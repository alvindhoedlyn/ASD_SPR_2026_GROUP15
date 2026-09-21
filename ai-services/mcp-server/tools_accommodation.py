"""
MCP tool implementations for the Accommodation feature (student-3 / RenzoRobin).

These functions are registered as MCP tools in server.py. They talk to the
student-RenzoRobin database service directly over HTTP.

IMPORTANT: This MCP server runs locally, NOT inside Docker. The database
service is containerised and only reachable inside the Docker network at
`student-RenzoRobin-database:6003`. For the MCP server (running on the host)
to reach it, the database service's port must be published to the host in
docker-compose.yml (e.g. "6003:6003"). Adjust ACCOMMODATION_DB_URL below if
your published host port differs.
"""

import os
import requests

ACCOMMODATION_DB_URL = os.environ.get("ACCOMMODATION_DB_URL", "http://localhost:6003")
REQUEST_TIMEOUT = 10


def _get(path: str, params: dict | None = None):
    url = f"{ACCOMMODATION_DB_URL}{path}"
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.ConnectionError as exc:
        return {"error": "accommodation database service unavailable", "detail": str(exc)}
    except requests.exceptions.Timeout as exc:
        return {"error": "accommodation database service timed out", "detail": str(exc)}

    try:
        body = resp.json()
    except ValueError:
        return {"error": "accommodation database returned invalid response", "detail": resp.text[:200]}

    if resp.status_code >= 400:
        return {"error": "accommodation database error", "status": resp.status_code, "detail": body}

    return body


def get_accommodations_by_city(city_area: str):
    """
    Purpose: Return accommodations located in a given city/area.
    Input: city_area (string, required)
    Output: list of accommodation records, or {"error": ...}
    """
    city_area = (city_area or "").strip()
    if not city_area:
        return {"error": "city_area is required"}

    return _get("/accommodations", params={"city": city_area})


def get_accommodation_details(accommodation_id: int):
    """
    Purpose: Return full details (including rooms) for one accommodation.
    Input: accommodation_id (int, required)
    Output: accommodation record, or {"error": ...}
    """
    if accommodation_id is None:
        return {"error": "accommodation_id is required"}

    details = _get(f"/accommodations/{accommodation_id}")
    if isinstance(details, dict) and "error" in details:
        return details

    rooms = _get(f"/accommodations/{accommodation_id}/rooms")
    if isinstance(rooms, dict) and "error" in rooms:
        rooms = []

    if isinstance(details, dict):
        details["rooms"] = rooms

    return details


if __name__ == "__main__":
    # Manual terminal validation (Terminal B in the lab pattern):
    # cd ai-services/mcp-server
    # python -c "from tools_accommodation import *; print(get_accommodations_by_city('Sydney'))"
    print(get_accommodations_by_city("Sydney"))
    print(get_accommodation_details(1))