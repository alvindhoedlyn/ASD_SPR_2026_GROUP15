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
    "goal": "Validate Accommodation Recommender app behavior using a local AI-mode workflow",
    "checks": [
        "/accommodations",
        "/accommodations/{id}",
        "/accommodations/{id}/rooms",
        "/priorities/{user_id}",
        "/recommendations",
        "/recommendations/explain",
    ],
}


# Docker Compose exposes:
#   container port 5000 -> host port 5003
#
# Therefore the agentic loop running on Windows uses:
#   http://127.0.0.1:5003
BASE_URL = os.getenv(
    "APP_BASE_URL",
    "http://127.0.0.1:5003"
)


# If this agentic loop is running on Windows, Ollama is normally
# reachable through localhost.
#
# If you later run this agentic loop INSIDE Docker, change this to:
#   http://ai-mode:11434/v1
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434/v1"
)


IMPLEMENTATION_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:0.5b"
)

REVIEW_MODEL = os.getenv(
    "OLLAMA_REVIEW_MODEL",
    "llama3.1:8b"
)


# ============================================================
# HTTP HELPER
# ============================================================

def get_json(endpoint, timeout=10):
    """
    Perform a GET request and return:
        success, response_json, message
    """

    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(
            url,
            timeout=timeout
        )

        if response.status_code >= 400:
            return (
                False,
                None,
                f"{endpoint} -> HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        try:
            data = response.json()
        except ValueError:
            return (
                False,
                None,
                f"{endpoint} -> HTTP {response.status_code}, "
                "but response was not valid JSON"
            )

        return (
            True,
            data,
            f"{endpoint} -> HTTP {response.status_code}"
        )

    except requests.exceptions.ConnectionError:
        return (
            False,
            None,
            f"{endpoint} -> connection failed "
            f"(is Docker/Flask running on {BASE_URL}?)"
        )

    except requests.exceptions.Timeout:
        return (
            False,
            None,
            f"{endpoint} -> request timed out"
        )

    except Exception as exc:
        return (
            False,
            None,
            f"{endpoint} -> error: {exc}"
        )


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_accommodation(row):
    """
    Validate one accommodation returned by the API.
    """

    if not isinstance(row, dict):
        return False, "Accommodation record is not a JSON object"

    accommodation_id = row.get("accommodation_id")
    name = row.get("name")
    city_area = row.get("city_area")

    if not isinstance(accommodation_id, int):
        return False, "accommodation_id must be an integer"

    if not name:
        return False, "name is required"

    if not city_area:
        return False, "city_area is required"

    return True, "ok"


# ============================================================
# OBSERVE: ACCOMMODATIONS
# ============================================================

def observe_data_quality():
    """
    Validate accommodation data through the Flask API.

    This avoids directly opening app.db from Windows,
    which is stored inside the Docker volume.
    """

    ok, data, message = get_json("/accommodations")

    if not ok:
        return False, message

    # The endpoint may return a list directly.
    if isinstance(data, list):
        rows = data

    # Some APIs wrap the list in a JSON object.
    elif isinstance(data, dict):
        rows = (
            data.get("accommodations")
            or data.get("data")
            or data.get("results")
        )

        if rows is None:
            return (
                False,
                "/accommodations returned JSON, "
                "but no accommodation list was found"
            )

    else:
        return (
            False,
            "/accommodations returned an unexpected JSON format"
        )

    if len(rows) < 10:
        return (
            False,
            f"Expected at least 10 accommodations, "
            f"found {len(rows)}"
        )

    for index, row in enumerate(rows, start=1):
        valid, validation_message = validate_accommodation(row)

        if not valid:
            return (
                False,
                f"Accommodation #{index}: {validation_message}"
            )

    return (
        True,
        f"Data validation passed ({len(rows)} accommodations)"
    )


# ============================================================
# OBSERVE: ROOMS / PRICING
# ============================================================

def observe_room_pricing(accommodation_id=1):
    """
    Validate room pricing through:
        GET /accommodations/<id>/rooms
    """

    endpoint = f"/accommodations/{accommodation_id}/rooms"

    ok, data, message = get_json(endpoint)

    if not ok:
        return False, message

    if isinstance(data, list):
        rooms = data

    elif isinstance(data, dict):
        rooms = (
            data.get("rooms")
            or data.get("room_types")
            or data.get("data")
            or data.get("results")
        )

        if rooms is None:
            return (
                False,
                f"{endpoint} returned JSON, "
                "but no room list was found"
            )

    else:
        return (
            False,
            f"{endpoint} returned an unexpected JSON format"
        )

    if not rooms:
        return (
            False,
            f"No rooms found for accommodation_id "
            f"{accommodation_id}"
        )

    for room in rooms:
        if not isinstance(room, dict):
            return False, "Room record is not a JSON object"

        room_id = room.get("room_id")
        price = room.get("price_per_night")

        if price is None:
            return (
                False,
                f"Room {room_id} has no price_per_night"
            )

        try:
            numeric_price = float(price)
        except (TypeError, ValueError):
            return (
                False,
                f"Room {room_id} has a non-numeric price: {price}"
            )

        if numeric_price <= 0:
            return (
                False,
                f"Room {room_id} has an invalid price: {price}"
            )

    return (
        True,
        f"Room pricing validation passed for "
        f"accommodation_id {accommodation_id}"
    )


# ============================================================
# OBSERVE: DETAIL ENDPOINT
# ============================================================

def observe_accommodation_detail(accommodation_id=1):
    endpoint = f"/accommodations/{accommodation_id}"

    ok, data, message = get_json(endpoint)

    if not ok:
        return False, message

    if not isinstance(data, dict):
        return (
            False,
            f"{endpoint} returned an unexpected response format"
        )

    return True, f"{endpoint} -> detail endpoint valid"


# ============================================================
# OBSERVE: PRIORITIES
# ============================================================

def observe_priorities(user_id=1):
    endpoint = f"/priorities/{user_id}"

    ok, data, message = get_json(endpoint)

    if not ok:
        return False, message

    if not isinstance(data, (dict, list)):
        return (
            False,
            f"{endpoint} returned an unexpected response format"
        )

    return True, f"{endpoint} -> priorities endpoint valid"


# ============================================================
# OBSERVE: LIVE ENDPOINTS
# ============================================================

def observe_live_endpoints():
    results = []

    # --------------------------------------------------------
    # GET /accommodations
    # --------------------------------------------------------

    try:
        response = requests.get(
            f"{BASE_URL}/accommodations",
            timeout=10
        )

        results.append(
            f"/accommodations -> HTTP {response.status_code}"
        )

    except Exception as exc:
        results.append(
            f"/accommodations -> error: {exc}"
        )

    # --------------------------------------------------------
    # POST /recommendations
    # --------------------------------------------------------

    try:
        response = requests.post(
            f"{BASE_URL}/recommendations",
            json={
                "user_id": 1,
                "city": "Bali, Indonesia",
                "desired_facilities": [
                    "wifi",
                    "pool"
                ],
            },
            timeout=15
        )

        results.append(
            f"/recommendations -> HTTP {response.status_code}"
        )

    except Exception as exc:
        results.append(
            f"/recommendations -> error: {exc}"
        )

    # --------------------------------------------------------
    # POST /recommendations/explain
    # --------------------------------------------------------

    try:
        response = requests.post(
            f"{BASE_URL}/recommendations/explain",
            json={
                "user_id": 1,
                "city": "Bali, Indonesia",
                "desired_facilities": [
                    "wifi",
                    "pool"
                ],
            },
            timeout=15
        )

        results.append(
            f"/recommendations/explain -> "
            f"HTTP {response.status_code}"
        )

    except Exception as exc:
        results.append(
            f"/recommendations/explain -> error: {exc}"
        )

    return results


# ============================================================
# ACT: AI-MODE
# ============================================================

def call_model(
    model_name,
    system_prompt,
    user_prompt,
    max_tokens=150
):
    """
    Call the Ollama OpenAI-compatible API.
    """

    try:
        client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
            timeout=180.0,
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )

        content = response.choices[0].message.content

        if content and content.strip():
            return content.strip(), None

        return "No response generated.", None

    except Exception as exc:
        return (
            None,
            f"{model_name} unavailable or timed out: {exc}"
        )


def get_ai_mode_advice(observe_message):
    """
    Ask the local AI model to review the validation evidence.
    """

    prompt = (
        "You are the AI-MODE agent for a Flask "
        "Accommodation Recommender App.\n\n"

        "Current database fields:\n"
        "- accommodations: accommodation_id, name, city_area, "
        "description, facilities, avg_rating, review_count\n"
        "- room_types: room_id, accommodation_id, room_name, "
        "price_per_night, available_rooms, capacity\n\n"

        "Important domain rule:\n"
        "- An accommodation can have multiple room_types. "
        "Never recommend a unique price-per-accommodation constraint.\n\n"

        "Current endpoints:\n"
        "- GET /accommodations\n"
        "- GET /accommodations/<id>\n"
        "- GET /accommodations/<id>/rooms\n"
        "- GET /priorities/<user_id>\n"
        "- POST /recommendations\n"
        "- POST /recommendations/explain\n\n"

        f"Validation Evidence:\n{observe_message}\n\n"

        "Task:\n"
        "Review ONLY the recommendation-scoring and "
        "room-pricing behavior.\n\n"

        "Use the validation evidence provided. "
        "Prefer live endpoint evidence when available.\n\n"

        "Rules:\n"
        "- Do not invent new database fields.\n"
        "- Do not invent new endpoints.\n"
        "- Do not modify endpoint contracts.\n"
        "- Do not suggest new application features.\n"
        "- Focus only on validation, error handling, "
        "response formatting, or testing.\n"
        "- If the evidence does not support an improvement, write: "
        "No evidence-backed improvement identified.\n"
        "- Return exactly two bullet points, or the "
        "no-evidence sentence.\n"
    )

    return call_model(
        IMPLEMENTATION_MODEL,
        (
            "You are a concise implementation assistant. "
            "Follow the rules exactly. "
            "Do not invent requirements."
        ),
        prompt,
        max_tokens=150,
    )


# ============================================================
# ADAPT
# ============================================================

def adapt(
    ok_data,
    ok_detail,
    ok_rooms,
    ok_priorities,
    live_results,
    advice_available
):
    print()

    if not ok_data:
        print(
            "ADAPT: Accommodation data validation failed — "
            "check the Flask API/database seed data and rerun."
        )

    elif not ok_rooms:
        print(
            "ADAPT: Room pricing validation failed — "
            "check room_types data and pricing logic, then rerun."
        )

    elif not ok_detail:
        print(
            "ADAPT: Accommodation detail endpoint validation failed — "
            "check the endpoint implementation and rerun."
        )

    elif not ok_priorities:
        print(
            "ADAPT: Priorities endpoint validation failed — "
            "check the endpoint implementation and rerun."
        )

    elif not advice_available:
        print(
            "ADAPT: AI-Mode unavailable — "
            "check Ollama is running and the model is pulled, "
            "then rerun validation."
        )

    else:
        print(
            "ADAPT: Apply any AI-Mode suggestions to "
            "error handling/validation and rerun the loop."
        )

    print()
    print("Endpoint evidence:")
    for result in live_results:
        print(f"  - {result}")


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    print("=" * 70)
    print("RELEASE 0 AGENTIC LOOP — Accommodation Recommender")
    print("=" * 70)

    # --------------------------------------------------------
    # PLAN
    # --------------------------------------------------------

    print()
    print("PLAN")
    print(PLAN)

    # --------------------------------------------------------
    # ACT
    # --------------------------------------------------------

    print()
    print("ACT")
    print(
        "Check Flask API data, room pricing, "
        "and live recommendation endpoints"
    )

    print()
    print(f"Application URL: {BASE_URL}")

    # --------------------------------------------------------
    # OBSERVE
    # --------------------------------------------------------

    ok_data, msg_data = observe_data_quality()

    ok_detail, msg_detail = observe_accommodation_detail(
        accommodation_id=1
    )

    ok_rooms, msg_rooms = observe_room_pricing(
        accommodation_id=1
    )

    ok_priorities, msg_priorities = observe_priorities(
        user_id=1
    )

    live_results = observe_live_endpoints()

    print()
    print("OBSERVE")

    print(f"- {msg_data}")
    print(f"- {msg_detail}")
    print(f"- {msg_rooms}")
    print(f"- {msg_priorities}")

    print()
    print("Live endpoint checks:")

    for result in live_results:
        print(f"- {result}")

    observe_message = (
        f"{msg_data}. "
        f"{msg_detail}. "
        f"{msg_rooms}. "
        f"{msg_priorities}. "
        "Live endpoint checks: "
        + "; ".join(live_results)
    )

    # --------------------------------------------------------
    # AI-MODE AGENT
    # --------------------------------------------------------

    print()
    print("AI-MODE AGENT")
    print(f"Model: {IMPLEMENTATION_MODEL}")
    print(f"Ollama URL: {OLLAMA_BASE_URL}")

    advice, error = get_ai_mode_advice(
        observe_message
    )

    if advice:
        print()
        print(advice)
    else:
        print()
        print(error)

    # --------------------------------------------------------
    # ADAPT
    # --------------------------------------------------------

    adapt(
        ok_data=ok_data,
        ok_detail=ok_detail,
        ok_rooms=ok_rooms,
        ok_priorities=ok_priorities,
        live_results=live_results,
        advice_available=advice is not None,
    )

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()
    print("LOOP COMPLETE")


if __name__ == "__main__":
    main()
