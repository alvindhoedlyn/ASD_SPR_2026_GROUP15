"""
MCP validation collector for the Itinerary / Travel App feature (student-AlvindhoEdlyn).

Calls the MCP-backed routes on YOUR OWN running backend (student-AlvindhoEdlyn),
which is how the brief's "MCP interaction through frontend UI and backend/API"
requirement is satisfied end-to-end. This intentionally goes through the backend
(not directly to the stdio MCP server), so the evidence reflects the real request
path a user's frontend action takes - same approach as RenzoRobin's
mcp_collector.py for the Accommodation Recommender.

Returns (ok, evidence) matching the shared collector contract used by
db_collector.py / endpoints_collector.py / devops_collector.py.
"""
import os
from pathlib import Path

import requests

BACKEND_URL = os.environ.get("MCP_APP_BASE_URL", "http://localhost:5001")
REQUEST_TIMEOUT = 20
# Trip generation calls Ollama once per day of the trip, so it needs more room
# than a plain read - mirrors ITINERARY_GENERATE_TIMEOUT in tools_itinerary.py.
GENERATE_TIMEOUT = 60

# Fixed, known-good test inputs, mirroring RenzoRobin's approach: simple and
# stable so this collector's pass/fail reflects the MCP integration itself,
# not query design. journey_id 1 is guaranteed to exist per the database's
# seed data, and duration=2 keeps the Ollama round trip short.
TEST_JOURNEY_ID = 1
TEST_DURATION = 2
TEST_PREFERENCES = "food and museums"

# generate_trip_itinerary is the one MCP tool that writes data, so its mirror
# route requires a verified session (get_current_user_id() in app.py) - the
# same auth the real frontend uses. There's no safe fixed test credential to
# hardcode here (unlike available_journeys, which is a public read), so this
# collector accepts a pre-obtained session token via env var instead of
# guessing at shared-backend's login contract.
#
# To exercise the write path: log in as a seeded test account through the
# app once, copy its jb_token out of localStorage, and export it before
# running the loop:
#     export MCP_TEST_SESSION_TOKEN=<token>
#
# Without it, that one check is SKIPPED and reported as such (never silently
# passed) - overall pass/fail then rests on the two read-only tools.
TEST_SESSION_TOKEN = os.environ.get("MCP_TEST_SESSION_TOKEN", "").strip()


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines = []
    all_ok = True

    # ---- Tool 1: /mcp/tools (tool listing) ----
    try:
        resp = requests.get(f"{BACKEND_URL}/mcp/tools", timeout=REQUEST_TIMEOUT)
        if resp.status_code == 403:
            all_ok = False
            lines.append("mcp/tools: MCP mode is disabled on the backend.")
        elif resp.status_code != 200:
            all_ok = False
            lines.append(f"mcp/tools: HTTP {resp.status_code} — {resp.text[:200]}")
        else:
            body = resp.json()
            tools = body.get("tools")
            if isinstance(tools, list) and len(tools) > 0:
                names = ", ".join(t.get("name", "?") for t in tools)
                lines.append(f"mcp/tools: OK, {len(tools)} tool(s) listed ({names}).")
            else:
                all_ok = False
                lines.append(f"mcp/tools: unexpected result shape — {body}")
    except requests.exceptions.RequestException as exc:
        all_ok = False
        lines.append(f"mcp/tools: request failed — {exc}")

    # ---- Tool 2: available_journeys ----
    try:
        resp = requests.post(
            f"{BACKEND_URL}/mcp/available-journeys",
            json={},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 403:
            all_ok = False
            lines.append("available_journeys: MCP mode is disabled on the backend.")
        elif resp.status_code != 200:
            all_ok = False
            lines.append(f"available_journeys: HTTP {resp.status_code} — {resp.text[:200]}")
        else:
            body = resp.json()
            result = body.get("result")
            if isinstance(result, list):
                lines.append(
                    f"available_journeys: OK, tool={body.get('tool')}, "
                    f"returned {len(result)} journey(s)."
                )
            else:
                all_ok = False
                lines.append(f"available_journeys: unexpected result shape — {body}")
    except requests.exceptions.RequestException as exc:
        all_ok = False
        lines.append(f"available_journeys: request failed — {exc}")

    # ---- Tool 3: generate_trip_itinerary (write path, needs a session) ----
    if not TEST_SESSION_TOKEN:
        lines.append(
            "generate_trip_itinerary: SKIPPED — no MCP_TEST_SESSION_TOKEN set, "
            "so the authenticated write path wasn't exercised. Set that env "
            "var to a real session token to cover this tool."
        )
    else:
        try:
            resp = requests.post(
                f"{BACKEND_URL}/mcp/generate-trip-itinerary",
                json={
                    "journey_id": TEST_JOURNEY_ID,
                    "duration": TEST_DURATION,
                    "preferences": TEST_PREFERENCES,
                },
                headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"},
                timeout=GENERATE_TIMEOUT,
            )
            if resp.status_code == 403:
                all_ok = False
                lines.append("generate_trip_itinerary: MCP mode is disabled on the backend.")
            elif resp.status_code == 401:
                all_ok = False
                lines.append("generate_trip_itinerary: session token was rejected (expired/invalid).")
            elif resp.status_code != 200:
                all_ok = False
                lines.append(f"generate_trip_itinerary: HTTP {resp.status_code} — {resp.text[:200]}")
            else:
                body = resp.json()
                result = body.get("result", {})
                days = result.get("days", [])
                if isinstance(days, list) and len(days) == TEST_DURATION:
                    lines.append(
                        f"generate_trip_itinerary: OK, tool={body.get('tool')}, "
                        f"trip_id={result.get('trip_id')}, {len(days)} day(s) generated."
                    )
                else:
                    all_ok = False
                    lines.append(f"generate_trip_itinerary: unexpected result shape — {body}")
        except requests.exceptions.RequestException as exc:
            all_ok = False
            lines.append(f"generate_trip_itinerary: request failed — {exc}")

    evidence = "\n".join(lines)
    return all_ok, evidence