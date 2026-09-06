"""HTTP client for the Budget Tracker database microservice."""

import os

import requests


DATABASE_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://localhost:5702"
)


def _request(method, path, **kwargs):
    """
    Send an HTTP request to the database microservice.

    Returns JSON when available.
    Returns None for HTTP 204 responses.
    """

    response = requests.request(
        method,
        f"{DATABASE_SERVICE_URL}{path}",
        timeout=5,
        **kwargs,
    )

    response.raise_for_status()

    if response.status_code == 204:
        return None

    return response.json()


# =========================================================
# Expense API
# =========================================================

def get_expenses():
    return _request(
        "GET",
        "/expenses"
    )


def get_expense(expense_id):
    return _request(
        "GET",
        f"/expenses/{expense_id}"
    )


def create_expense(payload):
    return _request(
        "POST",
        "/expenses",
        json=payload
    )


def update_expense(expense_id, payload):
    return _request(
        "PUT",
        f"/expenses/{expense_id}",
        json=payload
    )


def delete_expense(expense_id):
    return _request(
        "DELETE",
        f"/expenses/{expense_id}"
    )


# =========================================================
# Budget API
# =========================================================

def get_budget():
    return _request(
        "GET",
        "/budget"
    )


def save_budget(payload):
    return _request(
        "POST",
        "/budget",
        json=payload
    )