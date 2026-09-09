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


# Backend running on local host port (Default: 6001 as defined in init_db.py)
BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:6001")


# Local Ollama endpoint
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")


IMPLEMENTATION_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
REVIEW_MODEL = os.getenv("OLLAMA_REVIEW_MODEL", "llama3.1:8b")


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
# MAIN LOOP
# ============================================================

def main():
    print("=" * 70)
    print("RELEASE 0 AGENTIC LOOP — Travel Itinerary Planner")
    print("=" * 70)

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


if __name__ == "__main__":
    main()