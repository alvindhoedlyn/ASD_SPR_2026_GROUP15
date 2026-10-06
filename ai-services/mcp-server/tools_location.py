"""
MCP tool implementations for the Attraction Recommender feature.
The shared MCP server runs locally. The containerised attraction database
is available through its published host port 6004.
"""

import os

import requests


LOCATION_DB_URL = os.getenv(
    "LOCATION_DB_URL",
    "http://localhost:6004"
)

REQUEST_TIMEOUT = 10


def _get(path, params=None):
    url = f"{LOCATION_DB_URL}{path}"

    try:
        response = requests.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
    except requests.ConnectionError as error:
        return {
            "error": "Attraction database service is unavailable",
            "details": str(error)
        }
    except requests.Timeout as error:
        return {
            "error": "Attraction database request timed out",
            "details": str(error)
        }

    try:
        response_data = response.json()
    except ValueError:
        return {
            "error": "Attraction database returned invalid JSON",
            "status": response.status_code
        }

    if response.status_code >= 400:
        return {
            "error": "Attraction database request failed",
            "status": response.status_code,
            "details": response_data
        }

    return response_data


def attractions_by_city(city, category=None):
    """
    Return attractions in a city, optionally filtered by category.
    """
    city = str(city or "").strip()
    category = str(category or "").strip()

    if not city:
        return {"error": "city is required"}

    attractions = _get("/places")

    if isinstance(attractions, dict) and "error" in attractions:
        return attractions

    matching_attractions = []

    for attraction in attractions:
        same_city = (
            attraction.get("city", "").strip().casefold()
            == city.casefold()
        )

        same_category = (
            not category
            or attraction.get(
                "category",
                ""
            ).strip().casefold() == category.casefold()
        )

        if same_city and same_category:
            matching_attractions.append(attraction)

    return {
        "city": city,
        "category": category or None,
        "count": len(matching_attractions),
        "attractions": matching_attractions
    }


def attraction_details(attraction_id):
    """
    Return the complete database record for one attraction.
    """
    try:
        attraction_id = int(attraction_id)
    except (TypeError, ValueError):
        return {
            "error": "attraction_id must be an integer"
        }

    if attraction_id < 1:
        return {
            "error": "attraction_id must be greater than zero"
        }

    return _get(f"/places/{attraction_id}")


if __name__ == "__main__":
    print(attractions_by_city("Sydney"))
    print(attractions_by_city("Sydney", "nature"))
    print(attraction_details(1))
