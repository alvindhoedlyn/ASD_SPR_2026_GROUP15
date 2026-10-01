"""RAG corpus loader for Student 5's Flight Recommender catalogue."""

import os

import requests


FLIGHT_DATABASE_URL = os.environ.get("FLIGHT_DATABASE_URL", "http://localhost:6005")
REQUEST_TIMEOUT = 10


def load_flight_chunks():
    """Build one independently grounded RAG chunk for each catalogue flight."""
    source_url = f"{FLIGHT_DATABASE_URL}/flights"
    try:
        response = requests.get(source_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        flights = response.json()
    except Exception as exc:
        return [{
            "chunk_id": "flight_source_unavailable",
            "source_id": "student-YajunNing-database:/flights",
            "authority_tier": "tier_1",
            "text": f"Flight catalogue unavailable: {exc}",
            "metadata": {"source_type": "flight_database", "error": True},
        }]

    chunks = []
    for flight in flights:
        flight_id = flight.get("id")
        stops = int(flight.get("stops", 0))
        stop_text = "direct with no stops" if stops == 0 else f"with {stops} stop(s)"
        text = (
            f"Flight: {flight.get('airline')} {flight.get('flight_number')}. "
            f"Route: {flight.get('origin')} to {flight.get('destination')}. "
            f"Departure time: {flight.get('departure_time')}. "
            f"Arrival time: {flight.get('arrival_time')}. "
            f"Price: AUD ${flight.get('price_aud')}. "
            f"Duration: {flight.get('duration_minutes')} minutes. "
            f"Stops: {stops}; this flight is {stop_text}."
        )
        chunks.append({
            "chunk_id": f"flight_{flight_id}",
            "source_id": f"student-YajunNing-database:/flights/{flight_id}",
            "authority_tier": "tier_1",
            "text": text,
            "metadata": {
                "source_type": "flight_database",
                "flight_id": flight_id,
                "flight_number": flight.get("flight_number"),
                "origin": flight.get("origin"),
                "destination": flight.get("destination"),
            },
        })
    return chunks
