"""
RAG corpus loader for the Attraction Recommender feature
Each attraction database record becomes one independently citable chunk
"""

import os

import requests


LOCATION_DB_URL = os.getenv(
    "LOCATION_DB_URL",
    "http://localhost:5404"
)

REQUEST_TIMEOUT = 10


def load_location_chunks():
    url = f"{LOCATION_DB_URL}/places"

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        attractions = response.json()
    except requests.RequestException as error:
        return [{
            "chunk_id": "location_source_unavailable",
            "source_id": (
                "student-TrongDao-database:/places"
            ),
            "authority_tier": "tier_1",
            "text": (
                "Attraction database unavailable: "
                f"{error}"
            ),
            "metadata": {
                "source_type": "attraction_database",
                "error": True
            }
        }]
    except ValueError as error:
        return [{
            "chunk_id": "location_source_invalid",
            "source_id": (
                "student-TrongDao-database:/places"
            ),
            "authority_tier": "tier_1",
            "text": (
                "Attraction database returned invalid JSON: "
                f"{error}"
            ),
            "metadata": {
                "source_type": "attraction_database",
                "error": True
            }
        }]

    chunks = []

    for attraction in attractions:
        attraction_id = attraction["attraction_id"]
        name = attraction["attraction_name"]
        city = attraction["city"]
        country = attraction["country"]
        category = attraction["category"]
        description = attraction["attraction_description"]
        cost = attraction["estimated_cost"]
        currency = attraction["currency"]
        duration = attraction["expected_duration_minutes"]
        environment = attraction["indoor_outdoor"]
        crowd_level = attraction["crowd_level"]
        friendliness = attraction[
            "beginner_friendliness_score"
        ]
        accessibility = attraction[
            "accessibility_information"
        ]

        cost_description = (
            f"free ({cost} {currency})"
            if float(cost) == 0
            else f"{cost} {currency}"
        )

        text = (
            f"Attraction: {name}, located in {city}, {country}. "
            f"Category: {category}. "
            f"Description: {description} "
            f"Estimated cost: {cost_description}. "
            f"Expected visit duration: {duration} minutes. "
            f"Environment: {environment}. "
            f"Crowd level: {crowd_level}. "
            f"Beginner friendliness: {friendliness} out of 5. "
            f"Accessibility information: {accessibility}"
        )

        chunks.append({
            "chunk_id": f"location_{attraction_id}",
            "source_id": (
                "student-TrongDao-database:"
                f"/places/{attraction_id}"
            ),
            "authority_tier": "tier_1",
            "text": text,
            "metadata": {
                "source_type": "attraction_database",
                "attraction_id": attraction_id,
                "city": city,
                "category": category
            }
        })

    return chunks