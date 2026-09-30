"""
MCP tool implementations for the Itinerary / Travel App feature (student-AlvindhoEdlyn).

These functions are registered as MCP tools in server.py.

IMPORTANT: This MCP server runs locally, NOT inside Docker. The services are
containerised, so the following ports must be published to the host in
docker-compose.yml:

    student-AlvindhoEdlyn-database:  "6001:6001"   (used by read-only tools)
    student-AlvindhoEdlyn-backend:   "5001:5001"   (used by trip generation)

Why two URLs?
- Reading journeys is a plain database read -> talk to the database (6001).
- Generating a trip needs the backend's logic (Ollama prompt, weather
  randomisation, saving to the DB) -> call the backend (5001) instead of
  duplicating that logic here.
"""

import json
import os
import requests

ITINERARY_DB_URL = os.environ.get("ITINERARY_DB_URL", "http://localhost:6001")
ITINERARY_BACKEND_URL = os.environ.get("ITINERARY_BACKEND_URL", "http://localhost:5001")

REQUEST_TIMEOUT = 10
# Generation calls Ollama once per day of the trip, so it needs a longer timeout.
GENERATE_TIMEOUT = int(os.environ.get("ITINERARY_GENERATE_TIMEOUT", "120"))

# Mirrors ACTIVITY_CATEGORIES in student-AlvindhoEdlyn/backend/app.py.
# Keep the two in sync if you change one.
ACTIVITY_CATEGORIES = {
    "Sightseeing": ["City tour", "Old town walk", "Harbor cruise", "Viewpoint photography"],
    "Adventure": ["Hiking trail", "Kayaking", "Snorkeling", "Rock climbing", "Bike rental"],
    "Culture": ["Museum visit", "Art gallery tour", "Historic site walk", "Local theater"],
    "Relaxation": ["Beach day", "Botanical gardens walk", "Spa visit", "Park picnic"],
    "Food & Drink": ["Local market tasting", "Cafe hopping", "Street food tour", "Cooking class"],
    "Shopping": ["Boutique shopping", "Souvenir hunting", "Craft market visit"],
}


def _request(method: str, base_url: str, path: str, timeout: int, **kwargs):
    """Shared HTTP helper. Always returns data or an {"error": ...} dict, never raises."""
    url = f"{base_url}{path}"
    try:
        resp = requests.request(method, url, timeout=timeout, **kwargs)
    except requests.exceptions.ConnectionError as exc:
        return {"error": "itinerary service unavailable", "detail": str(exc)}
    except requests.exceptions.Timeout as exc:
        return {"error": "itinerary service timed out", "detail": str(exc)}

    try:
        body = resp.json()
    except ValueError:
        return {"error": "itinerary service returned invalid response", "detail": resp.text[:200]}

    if resp.status_code >= 400:
        return {"error": "itinerary service error", "status": resp.status_code, "detail": body}

    return body


def get_available_journeys() -> str:
    """
    Purpose: List all pre-defined journeys a trip can be generated for.
    Input: none
    Output: JSON string - list of journeys (each has an id, label, locations),
            or {"error": ...}
    """
    result = _request("GET", ITINERARY_DB_URL, "/api/journeys", REQUEST_TIMEOUT)
    return json.dumps(result)


def generate_trip_itinerary(
    journey_id: int,
    duration: int,
    preferences: str = "General exploration",
    user_id: int = 1,
) -> str:
    """
    Purpose: Generate and save an AI-written day-by-day itinerary for a journey.
    Input: journey_id (int, required), duration in days (int, required, >= 1),
           preferences (str, optional), user_id (int, optional)
    Output: JSON string - the created trip (trip_id, label, days[...]),
            or {"error": ...}
    """
    try:
        journey_id = int(journey_id)
        duration = int(duration)
    except (TypeError, ValueError):
        return json.dumps({"error": "journey_id and duration must be integers"})

    if journey_id < 1:
        return json.dumps({"error": "journey_id must be at least 1"})
    if duration < 1 or duration > 14:
        return json.dumps({"error": "duration must be between 1 and 14"})

    payload = {
        "journeyId": journey_id,
        "duration": int(duration),
        "preferences": preferences or "General exploration",
        "userId": user_id,
    }
    result = _request(
        "POST", ITINERARY_BACKEND_URL, "/api/trips/generate", GENERATE_TIMEOUT, json=payload
    )
    return json.dumps(result)


def get_activity_categories() -> str:
    """
    Purpose: Return the activity categories (and example activities) used when
             generating itineraries.
    Input: none
    Output: JSON string - {category: [activities]}
    """
    return json.dumps(ACTIVITY_CATEGORIES, indent=2)


if __name__ == "__main__":
    # Manual terminal validation:
    # cd ai-services/mcp-server
    # python tools_itinerary.py
    print(get_available_journeys())
    print(get_activity_categories())
    print(generate_trip_itinerary(1, 2, "food and museums"))