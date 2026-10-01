"""Registered MCP tools for Student 5's Flight Recommender."""

import os
from typing import Any

import requests


FLIGHT_BACKEND_URL = os.environ.get("FLIGHT_BACKEND_URL", "http://localhost:5005")
FLIGHT_DATABASE_URL = os.environ.get("FLIGHT_DATABASE_URL", "http://localhost:6005")
REQUEST_TIMEOUT = 10


def _json_or_error(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"error": "The Flight service returned a non-JSON response."}


def recommend_flights(
    origin: str,
    destination: str,
    departure_date: str,
    max_budget: float,
    preference: str = "best_overall",
    return_date: str = "",
) -> dict[str, Any]:
    """Run the bounded Flight Recommender and return structured catalogue results."""
    payload = {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date or None,
        "max_budget": max_budget,
        "preference": preference,
        "ai_mode": False,
    }
    try:
        response = requests.post(
            f"{FLIGHT_BACKEND_URL}/api/flight-searches",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        body = _json_or_error(response)
        if not response.ok:
            return {
                "status": "error",
                "tool": "recommend_flights",
                "http_status": response.status_code,
                "error": body.get("error", "Flight recommendation failed"),
            }
        return {
            "status": "success",
            "tool": "recommend_flights",
            "input": payload,
            "result": body,
        }
    except requests.RequestException as exc:
        return {
            "status": "error",
            "tool": "recommend_flights",
            "error": f"Flight backend unavailable: {exc}",
        }


def get_flight_details(flight_id: int) -> dict[str, Any]:
    """Return one read-only flight catalogue record by database identifier."""
    if flight_id <= 0:
        return {
            "status": "error",
            "tool": "flight_details",
            "error": "flight_id must be a positive integer",
        }

    try:
        response = requests.get(
            f"{FLIGHT_DATABASE_URL}/flights/{flight_id}",
            timeout=REQUEST_TIMEOUT,
        )
        body = _json_or_error(response)
        if not response.ok:
            return {
                "status": "error",
                "tool": "flight_details",
                "http_status": response.status_code,
                "error": body.get("error", "Flight lookup failed"),
            }
        return {
            "status": "success",
            "tool": "flight_details",
            "result": body,
        }
    except requests.RequestException as exc:
        return {
            "status": "error",
            "tool": "flight_details",
            "error": f"Flight database unavailable: {exc}",
        }
