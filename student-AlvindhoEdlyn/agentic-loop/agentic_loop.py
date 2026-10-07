import importlib.util
import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=ENV_PATH)


PLAN = {
    "goal": "Validate Travel Itinerary Planner API behavior using a local AI-mode workflow",
    "checks": [
        "GET /api/journeys",
        "GET /api/journeys/{id}",
        "GET /api/trips",
        "GET /api/trips/{id}/details",
        "GET /api/trips/{id}/days",
        "POST /api/trips",
        "PUT /api/trips/{id}",
        "PUT /api/trips/{id}/days/{day_num}",
        "DELETE /api/trips/{id}/days/{day_num}",
        "DELETE /api/trips/{id}",
    ],
}

MCP_PLAN = {
    "goal": "Validate MCP tool-call behavior for the Travel Itinerary Planner's MCP mirror routes",
    "checks": [
        "GET /mcp/tools",
        "POST /mcp/available-journeys",
        "POST /mcp/generate-trip-itinerary",
    ],
}

RAG_PLAN = {
    "goal": "Validate RAG tool-call behavior for the Travel Itinerary Planner's RAG mirror routes",
    "checks": [
        "POST /rag/refresh",
        "POST /rag/retrieve",
        "POST /rag/activities",
    ],
}

# Database service - the "Endpoint testing" flow talks directly to the DB
# layer's own CRUD routes (bypasses the backend's auth/business logic).
BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:6001")

# Local Ollama endpoint
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

IMPLEMENTATION_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
REVIEW_MODEL = os.getenv("OLLAMA_REVIEW_MODEL", "llama3.1:8b")


# ============================================================
# LOAD THE MCP / RAG COLLECTORS + PIPELINES AS LOCAL MODULES
# ============================================================
# Same pattern RenzoRobin's agentic_loop/main.py uses to load its
# collectors/pipelines: importlib.util against an explicit file path,
# rather than a package-relative import. That keeps this script runnable
# directly (python agentic_loop.py) without needing __init__.py files or
# this folder to be on sys.path as a package.
#
# Matches the actual project layout:
#   student-AlvindhoEdlyn/agentic-loop/collector/mcp_collector.py
#   student-AlvindhoEdlyn/agentic-loop/collector/rag_collector.py
#   student-AlvindhoEdlyn/agentic-loop/pipeline/mcp_pipeline.py
#   student-AlvindhoEdlyn/agentic-loop/pipeline/rag_pipeline.py

THIS_FILE = Path(__file__).resolve()
AGENTIC_LOOP_DIR = THIS_FILE.parent
REPO_ROOT = AGENTIC_LOOP_DIR.parent.parent  # student-AlvindhoEdlyn/.. -> repo root (ASD_SPR_2026_GROUP15)


def _load_local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mcp_collector = _load_local_module(
    "alvindhoedlyn_mcp_collector", AGENTIC_LOOP_DIR / "collector" / "mcp_collector.py"
)
rag_collector = _load_local_module(
    "alvindhoedlyn_rag_collector", AGENTIC_LOOP_DIR / "collector" / "rag_collector.py"
)
mcp_pipeline = _load_local_module(
    "alvindhoedlyn_mcp_pipeline", AGENTIC_LOOP_DIR / "pipeline" / "mcp_pipeline.py"
)
rag_pipeline = _load_local_module(
    "alvindhoedlyn_rag_pipeline", AGENTIC_LOOP_DIR / "pipeline" / "rag_pipeline.py"
)


# ============================================================
# HTTP HELPER
# ============================================================

def get_json(endpoint, timeout=10):
    """Perform a GET request and return: (success, response_json, message)"""
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(url, timeout=timeout)

        if response.status_code >= 400:
            return (
                False,
                None,
                f"{endpoint} -> HTTP {response.status_code}: {response.text[:300]}",
            )

        try:
            data = response.json()
        except ValueError:
            return (
                False,
                None,
                f"{endpoint} -> HTTP {response.status_code}, but response was not valid JSON",
            )

        return (True, data, f"{endpoint} -> HTTP {response.status_code}")

    except requests.exceptions.ConnectionError:
        return (
            False,
            None,
            f"{endpoint} -> Connection failed (is Flask server running on {BASE_URL}?)",
        )
    except requests.exceptions.Timeout:
        return (False, None, f"{endpoint} -> Request timed out")
    except Exception as exc:
        return (False, None, f"{endpoint} -> Error: {exc}")


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_journey(row):
    """Validate a journey object returned by the API."""
    if not isinstance(row, dict):
        return False, "Journey record is not a JSON object"

    journey_id = row.get("journey_id")
    label = row.get("label")
    locations = row.get("locations")

    if not isinstance(journey_id, int):
        return False, "journey_id must be an integer"
    if not label or not isinstance(label, str):
        return False, "label is required and must be a string"
    if not isinstance(locations, list):
        return False, "locations must be a list"

    return True, "ok"


def validate_trip_day(day):
    """Validate a single day record returned within a trip itinerary."""
    if not isinstance(day, dict):
        return False, "Day record is not a JSON object"

    if "day_ID" not in day and "day_id" not in day:
        return False, "day_ID key missing"
    if not day.get("weather"):
        return False, "weather field missing or empty"
    if not day.get("itinerary"):
        return False, "itinerary field missing or empty"
    if not day.get("activity"):
        return False, "activity field missing or empty"

    return True, "ok"


# ============================================================
# OBSERVE: JOURNEYS
# ============================================================

def observe_journeys():
    """Validate journey seed data through GET /api/journeys."""
    ok, data, message = get_json("/api/journeys")

    if not ok:
        return False, message

    if not isinstance(data, list):
        return False, "/api/journeys returned an unexpected JSON format (expected list)"

    if len(data) < 10:
        return False, f"Expected at least 10 seeded journeys, found {len(data)}"

    for index, row in enumerate(data, start=1):
        valid, validation_message = validate_journey(row)
        if not valid:
            return False, f"Journey #{index}: {validation_message}"

    return True, f"Journeys validation passed ({len(data)} journeys present)"


# ============================================================
# OBSERVE: TRIPS & DAYS
# ============================================================

def observe_trips():
    """Validate default trip and days through GET /api/trips and GET /api/trips/1/days."""
    ok, data, message = get_json("/api/trips")
    if not ok:
        return False, message

    if not isinstance(data, list) or len(data) == 0:
        return False, "/api/trips returned empty or invalid data"

    # Check trip days for default trip 1
    ok_days, days_data, days_msg = get_json("/api/trips/1/days")
    if not ok_days:
        return False, days_msg

    if not isinstance(days_data, list) or len(days_data) == 0:
        return False, "Trip 1 has no associated itinerary days"

    for day in days_data:
        valid, err_msg = validate_trip_day(day)
        if not valid:
            return False, f"Trip Day check failed: {err_msg}"

    return True, f"Trips and itinerary days validation passed ({len(days_data)} days checked)"


# ============================================================
# OBSERVE: LIVE CRUD ENDPOINTS
# ============================================================

def observe_live_endpoints():
    """Perform quick state-mutating API checks for Trip CRUD operations."""
    results = []

    # 1. GET /api/journeys/1
    try:
        res = requests.get(f"{BASE_URL}/api/journeys/1", timeout=10)
        results.append(f"GET /api/journeys/1 -> HTTP {res.status_code}")
    except Exception as exc:
        results.append(f"GET /api/journeys/1 -> Error: {exc}")

    # 2. POST /api/trips (Create temporary trip)
    new_trip_id = None
    try:
        payload = {
            "user_id": 99,
            "journey_id": 2,
            "duration": 1,
            "days": [
                {
                    "day_number": 1,
                    "location": "Melbourne",
                    "weather": "Sunny",
                    "itinerary": "Coffee Tasting",
                    "activity": "Food & Drink",
                }
            ],
        }
        res = requests.post(f"{BASE_URL}/api/trips", json=payload, timeout=10)
        results.append(f"POST /api/trips -> HTTP {res.status_code}")
        if res.status_code == 201:
            new_trip_id = res.json().get("trip_id")
    except Exception as exc:
        results.append(f"POST /api/trips -> Error: {exc}")

    # 3. PUT /api/trips/<id>/days/1 (Update day)
    if new_trip_id:
        try:
            update_payload = {
                "weather": "Clear",
                "itinerary": "Dinner in Southbank",
                "activity": "Food & Drink",
            }
            res = requests.put(
                f"{BASE_URL}/api/trips/{new_trip_id}/days/1",
                json=update_payload,
                timeout=10,
            )
            results.append(f"PUT /api/trips/{new_trip_id}/days/1 -> HTTP {res.status_code}")
        except Exception as exc:
            results.append(f"PUT day -> Error: {exc}")

        # 4. DELETE /api/trips/<id> (Cleanup)
        try:
            res = requests.delete(f"{BASE_URL}/api/trips/{new_trip_id}", timeout=10)
            results.append(f"DELETE /api/trips/{new_trip_id} -> HTTP {res.status_code}")
        except Exception as exc:
            results.append(f"DELETE trip -> Error: {exc}")

    return results


# ============================================================
# ACT: AI-MODE
# ============================================================

def call_model(model_name, system_prompt, user_prompt, max_tokens=150):
    """Call the Ollama OpenAI-compatible API."""
    try:
        client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
            timeout=180.0,
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if content and content.strip():
            return content.strip(), None

        return "No response generated.", None

    except Exception as exc:
        return None, f"{model_name} unavailable or timed out: {exc}"


def get_ai_mode_advice(observe_message):
    """Ask the local AI model to review the validation evidence."""
    prompt = (
        "You are the AI-MODE agent for a Flask Travel Itinerary Planner App.\n\n"
        "Current Database Schema:\n"
        "- journey: journey_ID, label, locations (JSON array)\n"
        "- trip: trip_ID, user_ID, journey_ID, duration, preferences\n"
        "- day: day_ID, trip_ID, weather, itinerary, activity\n\n"
        "Current API Endpoints:\n"
        "- GET /api/journeys, GET /api/journeys/<id>\n"
        "- GET /api/trips, GET /api/trips/<id>/details, GET /api/trips/<id>/days\n"
        "- POST /api/trips\n"
        "- PUT /api/trips/<id>, PUT /api/trips/<id>/days/<day_number>\n"
        "- DELETE /api/trips/<id>/days/<day_number>, DELETE /api/trips/<id>\n\n"
        f"Validation Evidence:\n{observe_message}\n\n"
        "Task:\n"
        "Review ONLY the database schema integrity, request validation, and endpoint responses.\n\n"
        "Rules:\n"
        "- Do not invent new database tables or fields.\n"
        "- Do not modify existing API contracts.\n"
        "- Focus on data validation, error handling, parameter sanitization, or transaction safety.\n"
        "- If the evidence shows no issues, respond with: 'No evidence-backed improvement identified.'\n"
        "- Otherwise, return exactly two bullet points outlining specific code improvements.\n"
    )

    return call_model(
        IMPLEMENTATION_MODEL,
        "You are a concise Flask code reviewer. Follow rules strictly.",
        prompt,
        max_tokens=150,
    )


# Fed into mcp_pipeline.build_implementation_prompt() as the task_prompt -
# the pipeline wraps this with "Review Scope", "Observed Evidence" and the
# reply-length instruction, so this only needs to state the task itself.
MCP_TASK_PROMPT = (
    "You are the AI-MODE agent for a Flask Travel Itinerary Planner App's MCP integration.\n\n"
    "MCP Mirror Routes (on the Flask backend, not the stdio MCP server):\n"
    "- GET /mcp/tools - lists available MCP tools\n"
    "- POST /mcp/available-journeys - mirrors the available_journeys MCP tool\n"
    "- POST /mcp/generate-trip-itinerary - mirrors the generate_trip_itinerary MCP tool "
    "(requires a verified session - Authorization: Bearer <token>)\n\n"
    "Task:\n"
    "Review ONLY the MCP tool-call behavior: whether MCP mode gating, authentication, "
    "and tool responses behaved correctly.\n\n"
    "Rules:\n"
    "- Do not invent new MCP tools or routes.\n"
    "- Do not modify existing API contracts.\n"
    "- Focus on MCP mode gating, auth handling, input validation, or response shape correctness.\n"
    "- If the evidence shows no issues, respond with: 'No evidence-backed improvement identified.'\n"
    "- Otherwise, return exactly two bullet points outlining specific code improvements."
)

# Fed into rag_pipeline.build_implementation_prompt() the same way.
RAG_TASK_PROMPT = (
    "You are the AI-MODE agent for a Flask Travel Itinerary Planner App's RAG integration.\n\n"
    "RAG Mirror Routes (on the Flask backend, not rag_http_server.py directly):\n"
    "- POST /rag/refresh - mirrors the refresh_corpus RAG tool (requires a verified session)\n"
    "- POST /rag/retrieve - mirrors the retrieve_context RAG tool (requires a verified session)\n"
    "- POST /rag/activities - mirrors the retrieve_activities RAG tool (requires a verified session)\n\n"
    "Task:\n"
    "Review ONLY the RAG tool-call behavior: whether RAG mode gating, authentication, "
    "and tool responses behaved correctly.\n\n"
    "Rules:\n"
    "- Do not invent new RAG tools or routes.\n"
    "- Do not modify existing API contracts.\n"
    "- Focus on RAG mode gating, auth handling, input validation, or response shape correctness.\n"
    "- If the evidence shows no issues, respond with: 'No evidence-backed improvement identified.'\n"
    "- Otherwise, return exactly two bullet points outlining specific code improvements."
)


# ============================================================
# ADAPT
# ============================================================

def adapt(ok_journeys, ok_trips, live_results, advice_available):
    print()
    if not ok_journeys:
        print("ADAPT: Journeys validation failed — check database/init_db.py seed data.")
    elif not ok_trips:
        print("ADAPT: Trips or Days validation failed — verify SQLite foreign keys and data.")
    elif not advice_available:
        print("ADAPT: AI-Mode unavailable — check Ollama connection and models.")
    else:
        print("ADAPT: Review any AI suggestions for improving exception handling or SQL transactions.")

    print("\nEndpoint evidence:")
    for result in live_results:
        print(f"  - {result}")


def adapt_tool_mode(mode_label, ok, evidence, advice_available):
    """Shared ADAPT step for the MCP and RAG tool-call modes - both collect
    evidence as a single newline-joined string and both gate on backend
    auth/mode checks, so one function covers both rather than duplicating
    near-identical adapt_mcp()/adapt_rag() copies."""
    print()
    if not ok:
        print(f"ADAPT: One or more {mode_label} checks failed — check {mode_label} mode, backend auth, or the mirror routes.")
    elif not advice_available:
        print("ADAPT: AI-Mode unavailable — check Ollama connection and models.")
    else:
        print(f"ADAPT: Review any AI suggestions for improving {mode_label} auth handling or input validation.")

    print(f"\n{mode_label} tool evidence:")
    for line in evidence.splitlines():
        print(f"  - {line}")


# ============================================================
# HUMAN REVIEW STEP
# ============================================================

def prompt_user_review():
    """Prompt the user to review the loop output and select an approval status."""
    print("\n" + "=" * 70)
    print("USER REVIEW")
    print("=" * 70)
    print("Please review the loop results above and select an option:")
    print("  [1] APPROVE          - The loop functioned correctly and results are satisfactory.")
    print("  [2] PARTIALLY APPROVE- The loop ran, but some checks or suggestions need adjustment.")
    print("  [3] DENY             - The loop failed or generated invalid results.")

    choices = {
        "1": ("APPROVE", "Loop approved by user. Proceeding with current configuration."),
        "2": ("PARTIALLY APPROVE", "Loop partially approved. Manual inspection or minor adjustments required."),
        "3": ("DENY", "Loop denied. Requires troubleshooting before re-running."),
    }

    while True:
        choice = input("\nEnter your choice (1, 2, or 3): ").strip()
        if choice in choices:
            status, note = choices[choice]
            print(f"\nReview Status: [{status}]")
            print(f"Note: {note}")
            return status

        print("Invalid choice. Please enter 1, 2, or 3.")


# ============================================================
# RUN: ENDPOINT TESTING (existing flow)
# ============================================================

def run_endpoint_testing():
    print("\nPLAN")
    print(PLAN)

    print("\nACT")
    print("Checking Flask API endpoints, database integrity, and trip CRUD actions...")
    print(f"Application URL: {BASE_URL}")

    # OBSERVE
    ok_journeys, msg_journeys = observe_journeys()
    ok_trips, msg_trips = observe_trips()
    live_results = observe_live_endpoints()

    print("\nOBSERVE")
    print(f"- {msg_journeys}")
    print(f"- {msg_trips}")

    print("\nLive endpoint checks:")
    for result in live_results:
        print(f"- {result}")

    observe_message = (
        f"{msg_journeys}. {msg_trips}. "
        f"Live checks: {'; '.join(live_results)}"
    )

    # AI-MODE AGENT
    print("\nAI-MODE AGENT")
    print(f"Model: {IMPLEMENTATION_MODEL}")
    print(f"Ollama URL: {OLLAMA_BASE_URL}")

    advice, error = get_ai_mode_advice(observe_message)

    if advice:
        print(f"\n{advice}")
    else:
        print(f"\n{error}")

    # ADAPT
    adapt(
        ok_journeys=ok_journeys,
        ok_trips=ok_trips,
        live_results=live_results,
        advice_available=advice is not None,
    )

    # USER REVIEW
    review_status = prompt_user_review()

    print("\nLOOP COMPLETE")
    print(f"Final Outcome: {review_status}")


# ============================================================
# RUN: MCP TESTING (delegated to collector/mcp_collector.py + pipeline/mcp_pipeline.py)
# ============================================================

def run_mcp_testing():
    print("\nPLAN")
    print(MCP_PLAN)

    print("\nACT")
    print("Checking MCP mirror routes via mcp_collector...")

    # OBSERVE - shared collector contract: collect() returns (ok: bool, evidence: str)
    ok, evidence = mcp_collector.collect(AGENTIC_LOOP_DIR, REPO_ROOT)

    print("\nOBSERVE")
    for line in evidence.splitlines():
        print(f"- {line}")

    # AI-MODE AGENT - two-stage implementation + review via mcp_pipeline
    print("\nAI-MODE AGENT (Implementation)")
    print(f"Model: {IMPLEMENTATION_MODEL}")
    print(f"Ollama URL: {OLLAMA_BASE_URL}")

    implementation_prompt = mcp_pipeline.build_implementation_prompt(MCP_TASK_PROMPT, evidence)
    implementation_output, impl_error = call_model(
        IMPLEMENTATION_MODEL,
        "You are a concise Flask/MCP code reviewer. Follow rules strictly.",
        implementation_prompt,
        max_tokens=150,
    )

    if implementation_output:
        print(f"\n{implementation_output}")
    else:
        print(f"\n{impl_error}")

    print("\nAI-MODE AGENT (Review)")
    print(f"Model: {REVIEW_MODEL}")

    if implementation_output:
        review_prompt = mcp_pipeline.build_review_prompt(implementation_output, evidence)
        review_output, review_error = call_model(
            REVIEW_MODEL,
            "You are a concise second-pass reviewer. Follow rules strictly.",
            review_prompt,
            max_tokens=100,
        )
        print(f"\n{review_output}" if review_output else f"\n{review_error}")
    else:
        print("\nSkipped - no implementation output to review.")

    # ADAPT
    adapt_tool_mode("MCP", ok, evidence, implementation_output is not None)

    # USER REVIEW
    review_status = prompt_user_review()

    print("\nLOOP COMPLETE")
    print(f"Final Outcome: {review_status}")


# ============================================================
# RUN: RAG TESTING (delegated to collector/rag_collector.py + pipeline/rag_pipeline.py)
# ============================================================

def run_rag_testing():
    print("\nPLAN")
    print(RAG_PLAN)

    print("\nACT")
    print("Checking RAG mirror routes via rag_collector...")

    # OBSERVE - shared collector contract: collect() returns (ok: bool, evidence: str)
    ok, evidence = rag_collector.collect(AGENTIC_LOOP_DIR, REPO_ROOT)

    print("\nOBSERVE")
    for line in evidence.splitlines():
        print(f"- {line}")

    # AI-MODE AGENT - two-stage implementation + review via rag_pipeline
    print("\nAI-MODE AGENT (Implementation)")
    print(f"Model: {IMPLEMENTATION_MODEL}")
    print(f"Ollama URL: {OLLAMA_BASE_URL}")

    implementation_prompt = rag_pipeline.build_implementation_prompt(RAG_TASK_PROMPT, evidence)
    implementation_output, impl_error = call_model(
        IMPLEMENTATION_MODEL,
        "You are a concise Flask/RAG code reviewer. Follow rules strictly.",
        implementation_prompt,
        max_tokens=150,
    )

    if implementation_output:
        print(f"\n{implementation_output}")
    else:
        print(f"\n{impl_error}")

    print("\nAI-MODE AGENT (Review)")
    print(f"Model: {REVIEW_MODEL}")

    if implementation_output:
        review_prompt = rag_pipeline.build_review_prompt(implementation_output, evidence)
        review_output, review_error = call_model(
            REVIEW_MODEL,
            "You are a concise second-pass reviewer. Follow rules strictly.",
            review_prompt,
            max_tokens=100,
        )
        print(f"\n{review_output}" if review_output else f"\n{review_error}")
    else:
        print("\nSkipped - no implementation output to review.")

    # ADAPT
    adapt_tool_mode("RAG", ok, evidence, implementation_output is not None)

    # USER REVIEW
    review_status = prompt_user_review()

    print("\nLOOP COMPLETE")
    print(f"Final Outcome: {review_status}")


# ============================================================
# MAIN LOOP
# ============================================================

def main():
    print("=" * 50)
    print("RELEASE 1 AGENTIC LOOP — Travel Itinerary Planner")
    print("=" * 50)

    while True:
        print("\n" + "=" * 50)
        print("MAIN MENU")
        print("=" * 50)
        print("  1 - Endpoint testing (existing)")
        print("  2 - MCP")
        print("  3 - RAG")
        print("  0 - Exit Loop")

        choice = input("\nChoose an option: ").strip()

        if choice == "0":
            print("Loop closed.")
            break
        elif choice == "1":
            run_endpoint_testing()
        elif choice == "2":
            run_mcp_testing()
        elif choice == "3":
            run_rag_testing()
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 0.")


if __name__ == "__main__":
    main()