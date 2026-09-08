"""
DB evidence collector for the Accommodation Recommender.

Queries the database microservice's own HTTP API rather than opening
the SQLite file directly. This matters because the database usually
runs inside Docker (with a named volume), where the .db file is not
reachable at any plain host filesystem path — but the service's HTTP
port (6003 by default, per docker-compose.yml) IS reachable from the
host. No LLM involved here — this is the OBSERVE stage.
"""
import os

import requests

DATABASE_BASE_URL_DEFAULT = "http://localhost:6003"
ROOM_SAMPLE_LIMIT = 10  # how many accommodations' rooms to spot-check, to keep this fast


def collect(app_dir, repo_root) -> tuple[bool, str]:
    base_url = os.getenv("DATABASE_BASE_URL", DATABASE_BASE_URL_DEFAULT)

    try:
        health = requests.get(f"{base_url}/health", timeout=3)
    except requests.exceptions.ConnectionError:
        return False, (
            f"Database service not reachable at {base_url}. "
            "Start it first (docker compose up student-RenzoRobin-database), "
            "or set DATABASE_BASE_URL if it's exposed on a different host/port."
        )
    except requests.exceptions.Timeout:
        return False, f"Database service at {base_url} timed out."

    if health.status_code != 200:
        return False, f"Database service health check returned {health.status_code}."

    try:
        accoms_resp = requests.get(f"{base_url}/accommodations", timeout=5)
        accoms_resp.raise_for_status()
        accommodations = accoms_resp.json()
    except Exception as exc:
        return False, f"Failed to fetch /accommodations: {exc}"

    accom_count = len(accommodations)
    if accom_count == 0:
        return False, "Database reachable but /accommodations returned zero rows."

    # Spot-check rooms for a sample of accommodations (not all, to keep this fast)
    sample = accommodations[:ROOM_SAMPLE_LIMIT]
    total_rooms_checked = 0
    null_or_zero_price_rooms = 0
    accoms_with_no_rooms = 0

    for accom in sample:
        accom_id = accom.get("accommodation_id")
        try:
            rooms_resp = requests.get(f"{base_url}/accommodations/{accom_id}/rooms", timeout=5)
            rooms_resp.raise_for_status()
            rooms = rooms_resp.json()
        except Exception:
            continue

        if not rooms:
            accoms_with_no_rooms += 1
        for room in rooms:
            total_rooms_checked += 1
            price = room.get("price_per_night")
            if price is None or price <= 0:
                null_or_zero_price_rooms += 1

    evidence = (
        f"Database evidence (via HTTP API at {base_url}): "
        f"{accom_count} total accommodations; "
        f"sampled {len(sample)} of them, checking their rooms: "
        f"{total_rooms_checked} rooms found, {null_or_zero_price_rooms} with "
        f"null/zero price_per_night, {accoms_with_no_rooms} accommodations with no rooms at all."
    )
    return True, evidence