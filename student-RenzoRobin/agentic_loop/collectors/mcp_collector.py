"""
MCP validation collector for the Accommodation Recommender.

Calls the two MCP-backed routes on YOUR OWN running backend
(student-RenzoRobin-backend), which is how the brief's "MCP interaction
through frontend UI and backend/API" requirement is satisfied end-to-end.
This intentionally goes through the backend (not directly to the MCP
server), so the evidence reflects the real request path a user's frontend
action takes.

Returns (ok, evidence) matching the shared collector contract used by
db_collector.py / endpoints_collector.py / devops_collector.py.
"""
from pathlib import Path

import requests

BACKEND_URL = "http://localhost:5003"
REQUEST_TIMEOUT = 20

# Fixed, known-good test inputs — deliberately simple and stable so this
# collector's pass/fail reflects the MCP integration itself, not query
# design. Kyoto and accommodation_id 1 are guaranteed to exist per the
# database's seed_data().
TEST_CITY = "Kyoto"
TEST_ACCOMMODATION_ID = 1


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines = []
    all_ok = True

    # ---- Tool 1: accommodations_by_city ----
    try:
        resp = requests.post(
            f"{BACKEND_URL}/mcp/accommodations-by-city",
            json={"city_area": TEST_CITY},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 403:
            all_ok = False
            lines.append(f"accommodations_by_city('{TEST_CITY}'): MCP mode is disabled on the backend.")
        elif resp.status_code != 200:
            all_ok = False
            lines.append(f"accommodations_by_city('{TEST_CITY}'): HTTP {resp.status_code} — {resp.text[:200]}")
        else:
            body = resp.json()
            result = body.get("result")
            if isinstance(result, list):
                lines.append(
                    f"accommodations_by_city('{TEST_CITY}'): OK, tool={body.get('tool')}, "
                    f"returned {len(result)} accommodation(s)."
                )
            else:
                all_ok = False
                lines.append(f"accommodations_by_city('{TEST_CITY}'): unexpected result shape — {body}")
    except requests.exceptions.RequestException as exc:
        all_ok = False
        lines.append(f"accommodations_by_city('{TEST_CITY}'): request failed — {exc}")

    # ---- Tool 2: accommodation_details ----
    try:
        resp = requests.post(
            f"{BACKEND_URL}/mcp/accommodation-details/{TEST_ACCOMMODATION_ID}",
            json={},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 403:
            all_ok = False
            lines.append(f"accommodation_details({TEST_ACCOMMODATION_ID}): MCP mode is disabled on the backend.")
        elif resp.status_code != 200:
            all_ok = False
            lines.append(f"accommodation_details({TEST_ACCOMMODATION_ID}): HTTP {resp.status_code} — {resp.text[:200]}")
        else:
            body = resp.json()
            result = body.get("result")
            if isinstance(result, dict) and "name" in result:
                lines.append(
                    f"accommodation_details({TEST_ACCOMMODATION_ID}): OK, tool={body.get('tool')}, "
                    f"name='{result.get('name')}', rooms={len(result.get('rooms', []))}."
                )
            else:
                all_ok = False
                lines.append(f"accommodation_details({TEST_ACCOMMODATION_ID}): unexpected result shape — {body}")
    except requests.exceptions.RequestException as exc:
        all_ok = False
        lines.append(f"accommodation_details({TEST_ACCOMMODATION_ID}): request failed — {exc}")

    evidence = "\n".join(lines)
    return all_ok, evidence