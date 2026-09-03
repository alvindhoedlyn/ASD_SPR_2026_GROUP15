"""HTTP client for the separately owned Flight database service."""

import os

import requests


DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://database-service:5001")


def database_request(method, path, **kwargs):
    return requests.request(
        method,
        f"{DATABASE_SERVICE_URL}{path}",
        timeout=5,
        **kwargs,
    )


def get_available_flights(max_budget=None):
    params = {"max_budget": max_budget} if max_budget is not None else None
    response = database_request("GET", "/flights", params=params)
    response.raise_for_status()
    return response.json()
