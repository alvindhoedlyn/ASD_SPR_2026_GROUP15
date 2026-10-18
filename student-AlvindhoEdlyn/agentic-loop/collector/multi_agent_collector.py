"""
Multi-agent validation collector for the Itinerary / Travel App feature (student-AlvindhoEdlyn).

Calls the /multi-agent/* mirror routes on YOUR OWN running backend (student-AlvindhoEdlyn),
same approach as rag_collector.py: goes through the backend (not directly to the shared
multi-agent server on port 5300), so the evidence reflects the real request path a user's
frontend action takes - including mode gating, session auth, input validation, workflow
ownership and the planner -> worker -> reviewer round itself.

What is checked, in order:
  1. Gating (needs no token): no session -> 401, mode switched off -> 403.
  2. Input validation (needs a token, no model calls): bad question / weather /
     journey_id, and a question that names no journey -> "insufficient_context".
  3. A real workflow round (needs a token, the shared server and Ollama - can take
     minutes): the journey and weather are inferred from the question, the result
     waits for human review, and each agent step reports its status.
  4. Ownership (GET by the owner, no token, and - if a second token is set - another
     user), then the human decision endpoint, including "already decided".

Side effect: step 3 leaves one workflow record in the shared server's history. The
collector closes it with an automated "reject" so nothing stays pending. That decision
is test cleanup only; it is separate from the human review the agentic loop asks for.

Returns (ok, evidence) matching the shared collector contract used by the other collectors.
"""
import os
from pathlib import Path

import requests

BACKEND_URL = os.environ.get("MCP_APP_BASE_URL", "http://localhost:5001").rstrip("/")
REQUEST_TIMEOUT = 30
# A real round runs three local-model steps (the backend itself waits up to 600 s).
WORKFLOW_TIMEOUT = float(os.environ.get("MULTI_AGENT_WORKFLOW_TIMEOUT", "660"))
RUN_FULL_WORKFLOW = os.environ.get("MULTI_AGENT_RUN_WORKFLOW", "true").strip().lower() in (
    "1", "true", "yes", "on"
)

# Fixed, known-good test input - this is test prompt 1 from the Multi-Server page. It names
# no journey label and no location, so it also proves the backend infers "Melbourne" and
# reads "rains" as Light Rain.
TEST_QUESTION = "What activities can I do in Melbourne if it rains?"
EXPECTED_WEATHER = "Light Rain"
# Outdoor activities the backend must have removed from the worker's options in Light Rain.
OUTDOOR_ACTIVITIES = {"Beach day", "Hiking trail", "Kayaking"}
MAX_QUESTION_CHARS = 1000  # the backend rejects anything longer

# Falls back to the RAG / MCP test tokens, since every route gates through the same shared
# session system - set whichever is convenient:
#     export MULTI_AGENT_TEST_SESSION_TOKEN=<token>
SESSION_TOKEN = (
    os.environ.get("MULTI_AGENT_TEST_SESSION_TOKEN", "").strip()
    or os.environ.get("RAG_TEST_SESSION_TOKEN", "").strip()
    or os.environ.get("MCP_TEST_SESSION_TOKEN", "").strip()
)
# Optional token of a DIFFERENT user, to prove one user cannot read or decide another's workflow.
OTHER_SESSION_TOKEN = os.environ.get("MULTI_AGENT_OTHER_SESSION_TOKEN", "").strip()

# What each unexpected status usually means, appended to the evidence line.
HINTS = {
    401: "session token was rejected (expired/invalid)",
    403: "multi-agent mode is disabled on the backend",
    502: "backend could not reach the database service or the shared multi-agent server",
    504: "the shared multi-agent server timed out",
}


def _short(body) -> str:
    return str(body)[:200]


def _call(method, path, token=None, payload=None, headers=None, timeout=REQUEST_TIMEOUT):
    """One request to the backend. Returns (status_code, body, error); error is a message
    when the request itself failed (connection refused, timeout, ...)."""
    request_headers = dict(headers or {})
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.request(
            method, f"{BACKEND_URL}{path}", json=payload, headers=request_headers, timeout=timeout
        )
    except requests.exceptions.RequestException as exc:
        return None, {}, f"{type(exc).__name__}: {exc}"
    try:
        body = resp.json() if resp.content else {}
    except ValueError:
        body = {}
    return resp.status_code, body, None


def _check(lines, label, expected, method, path, **kwargs):
    """Run one request and require an exact status code. Returns (passed, body)."""
    status, body, error = _call(method, path, **kwargs)
    if error:
        lines.append(f"{label} -> Error: {error}")
        return False, body
    if status == expected:
        lines.append(f"{label} -> HTTP {status} as expected")
        return True, body
    hint = f" ({HINTS[status]})" if status in HINTS else ""
    lines.append(f"{label} -> expected HTTP {expected}, got HTTP {status}{hint}: {_short(body)}")
    return False, body


def _step_summary(steps: dict) -> str:
    parts = []
    for name in ("planner", "worker", "reviewer"):
        step = steps.get(name) or {}
        parts.append(f"{name}={step.get('status', '?')}({step.get('model', '?')}, {step.get('elapsed_ms', '?')}ms)")
    return ", ".join(parts)


def _check_record(lines, record) -> bool:
    """Validate the shape and content of a workflow record. Returns True if it is sound."""
    ok = True
    steps = record.get("steps") or {}
    missing = [n for n in ("planner", "worker", "reviewer") if not (steps.get(n) or {}).get("output")]
    if missing:
        ok = False
        lines.append(f"workflow record -> missing output from: {', '.join(missing)}")
    if record.get("status") != "pending_human_review":
        ok = False
        lines.append(f"workflow record -> status is '{record.get('status')}', expected 'pending_human_review'")
    if (record.get("human_decision") or {}).get("status") != "pending":
        ok = False
        lines.append("workflow record -> human_decision is not 'pending' before a human has decided")
    if not record.get("caller"):
        ok = False
        lines.append("workflow record -> caller is empty (the audit log can't tell who asked)")

    evidence = record.get("evidence") or []
    if not evidence:
        ok = False
        lines.append(f"workflow record -> no evidence: the journey was not inferred from '{TEST_QUESTION}'")
    else:
        wrong_weather = [e.get("name") for e in evidence if e.get("weather") != EXPECTED_WEATHER]
        leaked = sorted({a for e in evidence for a in e.get("allowed_activities", []) if a in OUTDOOR_ACTIVITIES})
        if wrong_weather:
            ok = False
            lines.append(f"workflow evidence -> weather was not read as {EXPECTED_WEATHER} for: {', '.join(map(str, wrong_weather))}")
        if leaked:
            ok = False
            lines.append(f"workflow evidence -> outdoor activities offered in {EXPECTED_WEATHER}: {', '.join(leaked)}")
        if not wrong_weather and not leaked:
            names = ", ".join(str(e.get("name")) for e in evidence)
            lines.append(f"workflow evidence -> {len(evidence)} location(s) inferred ({names}), weather={EXPECTED_WEATHER}, no outdoor activities offered")
    if record.get("locations_without_weather"):
        ok = False
        lines.append(f"workflow record -> locations_without_weather={record['locations_without_weather']}, expected none")

    lines.append(f"workflow steps -> {_step_summary(steps)}")
    if record.get("degraded"):
        fell_back = [n for n in ("planner", "worker", "reviewer") if (steps.get(n) or {}).get("status") == "fallback"]
        # A fallback is a warning, not a route failure: the round still finished and reached review.
        lines.append(f"WARNING workflow degraded -> fallback used by: {', '.join(fell_back)} (check Ollama and the models)")
    return ok


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines = []
    all_ok = True

    # ---- 1. gating (no token needed) ----
    passed, _ = _check(lines, "POST /multi-agent/workflow (no session token)", 401,
                       "POST", "/multi-agent/workflow", payload={"question": TEST_QUESTION})
    all_ok &= passed
    passed, _ = _check(lines, "POST /multi-agent/workflow (X-Multi-Agent-Mode: off)", 403,
                       "POST", "/multi-agent/workflow", token=SESSION_TOKEN or None,
                       payload={"question": TEST_QUESTION}, headers={"X-Multi-Agent-Mode": "off"})
    all_ok &= passed

    if not SESSION_TOKEN:
        lines.append(
            "Remaining /multi-agent/* checks SKIPPED - no MULTI_AGENT_TEST_SESSION_TOKEN (or "
            "RAG_TEST_SESSION_TOKEN / MCP_TEST_SESSION_TOKEN) set. Every multi-agent route "
            "requires a verified session, so set one of those env vars to a real session "
            "token to exercise the rest of this collector."
        )
        return all_ok, "\n".join(lines)

    # ---- 2. input validation (no model calls) ----
    workflow = "POST /multi-agent/workflow"

    # The first validation request doubles as a session probe. If the token is rejected or
    # the mode is off, every later check would fail the same way - report it once and stop.
    status, body, error = _call("POST", "/multi-agent/workflow", token=SESSION_TOKEN, payload={})
    if error:
        lines.append(f"{workflow} (empty question) -> Error: {error}")
        lines.append("Remaining checks SKIPPED - the backend could not be reached.")
        return False, "\n".join(lines)
    if status in (401, 403):
        lines.append(f"{workflow} (empty question) -> HTTP {status} ({HINTS[status]})")
        lines.append("Remaining checks SKIPPED - fix the session token / multi-agent mode first.")
        return False, "\n".join(lines)
    if status == 400:
        lines.append(f"{workflow} (empty question) -> HTTP 400 as expected")
    else:
        all_ok = False
        lines.append(f"{workflow} (empty question) -> expected HTTP 400, got HTTP {status}: {_short(body)}")

    for label, payload, expected in [
        (f"(question over {MAX_QUESTION_CHARS} chars)", {"question": "x" * (MAX_QUESTION_CHARS + 1)}, 400),
        ("(unknown weather)", {"question": "Sydney Weekend", "weather": "Drizzly"}, 400),
        ("(journey_id not a number)", {"question": "Sydney Weekend", "journey_id": "abc"}, 400),
        ("(journey_id that does not exist)", {"question": "Sydney Weekend", "journey_id": 999999}, 404),
    ]:
        passed, _ = _check(lines, f"{workflow} {label}", expected, "POST", "/multi-agent/workflow",
                           token=SESSION_TOKEN, payload=payload)
        all_ok &= passed

    passed, body = _check(lines, f"{workflow} (names no journey or location)", 422, "POST",
                          "/multi-agent/workflow", token=SESSION_TOKEN,
                          payload={"question": "What should I do this weekend?"})
    all_ok &= passed
    if passed:
        journeys = body.get("available_journeys")
        if body.get("status") == "insufficient_context" and isinstance(journeys, list) and journeys:
            lines.append(f"{workflow} -> insufficient_context lists {len(journeys)} available journey(s)")
        else:
            all_ok = False
            lines.append(f"{workflow} -> 422 without status=insufficient_context and a journey list: {_short(body)}")

    # ---- 3. a real planner -> worker -> reviewer round ----
    if not RUN_FULL_WORKFLOW:
        lines.append("Full workflow checks SKIPPED - MULTI_AGENT_RUN_WORKFLOW is off.")
        return all_ok, "\n".join(lines)

    passed, record = _check(lines, f"{workflow} (full round: '{TEST_QUESTION}')", 200, "POST",
                            "/multi-agent/workflow", token=SESSION_TOKEN,
                            payload={"question": TEST_QUESTION}, timeout=WORKFLOW_TIMEOUT)
    all_ok &= passed
    workflow_id = record.get("workflow_id") if passed else None
    if not passed or not workflow_id:
        all_ok = False
        lines.append("Workflow read / ownership / decision checks SKIPPED - no workflow was created.")
        return all_ok, "\n".join(lines)

    all_ok &= _check_record(lines, record)

    # ---- 4. ownership and the human decision ----
    path = f"/multi-agent/workflow/{workflow_id}"
    passed, body = _check(lines, f"GET {path} (owner)", 200, "GET", path, token=SESSION_TOKEN)
    all_ok &= passed
    if passed and body.get("workflow_id") != workflow_id:
        all_ok = False
        lines.append(f"GET {path} -> returned a different workflow: {body.get('workflow_id')}")

    passed, _ = _check(lines, f"GET {path} (no session token)", 401, "GET", path)
    all_ok &= passed

    decision_path = f"{path}/decision"
    if OTHER_SESSION_TOKEN:
        passed, _ = _check(lines, f"GET {path} (another user)", 404, "GET", path, token=OTHER_SESSION_TOKEN)
        all_ok &= passed
        passed, _ = _check(lines, f"POST {decision_path} (another user)", 404, "POST", decision_path,
                           token=OTHER_SESSION_TOKEN, payload={"decision": "accept"})
        all_ok &= passed
    else:
        lines.append(
            "Ownership isolation checks SKIPPED - set MULTI_AGENT_OTHER_SESSION_TOKEN to "
            "another user's session token to prove users cannot read or decide each other's workflows."
        )

    passed, _ = _check(lines, f"POST {decision_path} (invalid decision)", 400, "POST", decision_path,
                       token=SESSION_TOKEN, payload={"decision": "maybe"})
    all_ok &= passed
    passed, _ = _check(lines, f"POST {decision_path} ('correct' without corrected_output)", 400, "POST",
                       decision_path, token=SESSION_TOKEN, payload={"decision": "correct"})
    all_ok &= passed

    # Automated cleanup decision - see the module docstring.
    passed, body = _check(lines, f"POST {decision_path} (reject, automated test cleanup)", 200, "POST",
                          decision_path, token=SESSION_TOKEN,
                          payload={"decision": "reject", "note": "automated multi_agent_collector test"})
    all_ok &= passed
    if passed and body.get("status") != "rejected":
        all_ok = False
        lines.append(f"POST {decision_path} -> status is '{body.get('status')}', expected 'rejected'")

    passed, _ = _check(lines, f"POST {decision_path} (second decision)", 409, "POST", decision_path,
                       token=SESSION_TOKEN, payload={"decision": "accept"})
    all_ok &= passed

    passed, body = _check(lines, f"GET {path} (after decision)", 200, "GET", path, token=SESSION_TOKEN)
    all_ok &= passed
    if passed and body.get("status") != "rejected":
        all_ok = False
        lines.append(f"GET {path} -> status is '{body.get('status')}' after the decision, expected 'rejected'")

    evidence = "\n".join(lines)
    return all_ok, evidence