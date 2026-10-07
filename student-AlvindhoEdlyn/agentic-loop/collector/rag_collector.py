"""
RAG validation collector for the Itinerary / Travel App feature (student-AlvindhoEdlyn).

Calls the RAG mirror routes on YOUR OWN running backend (student-AlvindhoEdlyn),
same approach as itinerary_mcp_collector.py for the MCP tools: goes through the
backend (not directly to rag_http_server.py), so the evidence reflects the real
request path a user's frontend action takes.

Every /rag/* mirror route requires a verified session (rag_request_guard() in
app.py calls get_current_user_id()) - unlike the MCP routes, where only the
write-path tool needed auth, there's no auth-free "safe read" tool here, so
every check below needs a session token.

Returns (ok, evidence) matching the shared collector contract used by
db_collector.py / endpoints_collector.py / devops_collector.py / itinerary_mcp_collector.py.
"""
import os
from pathlib import Path

import requests

BACKEND_URL = os.environ.get("MCP_APP_BASE_URL", "http://localhost:5001")
REQUEST_TIMEOUT = 30
REFRESH_TIMEOUT = 60  # corpus refresh can take longer than a plain query

# Fixed, known-good test inputs - simple and stable so pass/fail reflects the
# RAG integration itself, not query design. Bondi Beach / Light Rain mirror
# the example in rag_http_server.py's own docstring.
TEST_QUERY = "What can I do at Bondi Beach if it's raining?"
TEST_LOCATION = "Bondi Beach"
TEST_WEATHER = "Light Rain"

# Falls back to MCP_TEST_SESSION_TOKEN if RAG_TEST_SESSION_TOKEN isn't set,
# since both gate through the same shared-backend session system - set
# whichever is convenient:
#     export RAG_TEST_SESSION_TOKEN=<token>
RAG_TEST_SESSION_TOKEN = (
    os.environ.get("RAG_TEST_SESSION_TOKEN", "").strip()
    or os.environ.get("MCP_TEST_SESSION_TOKEN", "").strip()
)


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines = []
    all_ok = True

    if not RAG_TEST_SESSION_TOKEN:
        lines.append(
            "ALL /rag/* checks SKIPPED - no RAG_TEST_SESSION_TOKEN (or "
            "MCP_TEST_SESSION_TOKEN) set. Every RAG mirror route requires a "
            "verified session, so set one of those env vars to a real "
            "session token to exercise this collector."
        )
        return True, "\n".join(lines)

    headers = {"Authorization": f"Bearer {RAG_TEST_SESSION_TOKEN}"}

    # ---- /rag/refresh ----
    try:
        resp = requests.post(
            f"{BACKEND_URL}/rag/refresh", json={}, headers=headers, timeout=REFRESH_TIMEOUT
        )
        body = resp.json() if resp.content else {}
        if resp.status_code == 403:
            all_ok = False
            lines.append("POST /rag/refresh -> RAG mode is disabled on the backend")
        elif resp.status_code == 401:
            all_ok = False
            lines.append("POST /rag/refresh -> session token was rejected (expired/invalid)")
        elif resp.status_code != 200 or body.get("status") != "success":
            all_ok = False
            lines.append(f"POST /rag/refresh -> HTTP {resp.status_code}: {body}")
        else:
            chunk_count = body.get("chunk_count", "?")
            lines.append(f"POST /rag/refresh -> HTTP 200, corpus refreshed ({chunk_count} chunks)")
    except requests.exceptions.RequestException as exc:
        all_ok = False
        lines.append(f"POST /rag/refresh -> Error: {exc}")

    # ---- /rag/retrieve ----
    try:
        resp = requests.post(
            f"{BACKEND_URL}/rag/retrieve",
            json={"query": TEST_QUERY, "k": 5},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        body = resp.json() if resp.content else {}
        if resp.status_code == 403:
            all_ok = False
            lines.append("POST /rag/retrieve -> RAG mode is disabled on the backend")
        elif resp.status_code == 401:
            all_ok = False
            lines.append("POST /rag/retrieve -> session token was rejected (expired/invalid)")
        elif resp.status_code != 200 or body.get("status") != "success":
            all_ok = False
            lines.append(f"POST /rag/retrieve -> HTTP {resp.status_code}: {body}")
        else:
            results = body.get("results")
            if isinstance(results, list):
                lines.append(f"POST /rag/retrieve -> HTTP 200, {len(results)} result(s) for '{TEST_QUERY}'")
            else:
                all_ok = False
                lines.append(f"POST /rag/retrieve -> unexpected result shape — {body}")
    except requests.exceptions.RequestException as exc:
        all_ok = False
        lines.append(f"POST /rag/retrieve -> Error: {exc}")

    # ---- /rag/activities ----
    try:
        resp = requests.post(
            f"{BACKEND_URL}/rag/activities",
            json={"location": TEST_LOCATION, "weather": TEST_WEATHER, "k": 4},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        body = resp.json() if resp.content else {}
        if resp.status_code == 403:
            all_ok = False
            lines.append("POST /rag/activities -> RAG mode is disabled on the backend")
        elif resp.status_code == 401:
            all_ok = False
            lines.append("POST /rag/activities -> session token was rejected (expired/invalid)")
        elif resp.status_code == 404 and body.get("error") == "unknown_location":
            all_ok = False
            lines.append(
                f"POST /rag/activities -> unknown_location for '{TEST_LOCATION}' (check corpus seed data)"
            )
        elif resp.status_code != 200 or body.get("status") != "success":
            all_ok = False
            lines.append(f"POST /rag/activities -> HTTP {resp.status_code}: {body}")
        else:
            # NOTE: the exact key holding the result list (e.g. "activities" vs
            # "results") isn't confirmed from rag_http_server.py alone - it just
            # relays whatever retrieve_activities() in rag_pipeline.py returns.
            # Reporting whatever fields are present rather than assuming a
            # specific key name; tighten this once rag_pipeline.py's return
            # shape is confirmed.
            payload_fields = [k for k in body.keys() if k != "status"]
            lines.append(f"POST /rag/activities -> HTTP 200, status=success, fields={payload_fields}")
    except requests.exceptions.RequestException as exc:
        all_ok = False
        lines.append(f"POST /rag/activities -> Error: {exc}")

    evidence = "\n".join(lines)
    return all_ok, evidence