"""
Corpus loader for the Accommodation feature (student-3 / RenzoRobin).

Builds RAG chunks from the accommodation database service. This module is
registered in rag_pipeline.py's build_corpus(). Other students add their own
corpus_<feature>.py module and register it the same way, so the shared
corpus grows to cover every feature.

Reuses the existing /internal/accommodations-with-price endpoint, which
already returns name, city_area, description, facilities, avg_rating,
review_count, and min_price in a single call.
"""

import os
import requests

ACCOMMODATION_DB_URL = os.environ.get("ACCOMMODATION_DB_URL", "http://localhost:6003")
REQUEST_TIMEOUT = 10


def load_accommodation_chunks():
    """
    Returns a list of RAG chunk dicts for every accommodation, or a single
    diagnostic chunk if the database is unreachable (so refresh_corpus never
    silently produces zero accommodation chunks without a trace of why).
    """
    url = f"{ACCOMMODATION_DB_URL}/internal/accommodations-with-price"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        accommodations = resp.json()
    except Exception as exc:
        return [{
            "chunk_id": "accommodation_source_unavailable",
            "source_id": "student-RenzoRobin-database:/internal/accommodations-with-price",
            "authority_tier": "tier_1",
            "text": f"Accommodation database unavailable: {exc}",
            "metadata": {"source_type": "accommodation_database", "error": True},
        }]

    chunks = []
    for accom in accommodations:
        accom_id = accom.get("accommodation_id")
        name = accom.get("name", "Unknown")
        city = accom.get("city_area", "unknown location")
        description = accom.get("description") or ""
        facilities = accom.get("facilities") or []
        rating = accom.get("avg_rating")
        reviews = accom.get("review_count")
        min_price = accom.get("min_price")

        text = (
            f"Accommodation: {name} located in {city}. {description} "
            f"Facilities: {', '.join(facilities) if facilities else 'none listed'}. "
            f"Average rating {rating} from {reviews} reviews. "
            f"Starting price ${min_price} per night."
        )

        chunks.append({
            "chunk_id": f"accommodation_{accom_id}",
            "source_id": f"student-RenzoRobin-database:/accommodations/{accom_id}",
            "authority_tier": "tier_1",
            "text": text,
            "metadata": {
                "source_type": "accommodation_database",
                "accommodation_id": accom_id,
                "city_area": city,
            },
        })

    return chunks