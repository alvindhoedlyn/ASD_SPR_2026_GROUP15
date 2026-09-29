"""
Budget Tracker tools for the shared local MCP server.

These tools provide read-only access to Keyuan Gan's
Budget Tracker feature through its backend API.
"""

import os

import requests


BUDGET_BACKEND_URL = os.getenv(
    "BUDGET_BACKEND_URL",
    "http://localhost:5002"
)


def _get(path):
    """
    Send a GET request to the Budget Tracker backend.
    """

    response = requests.get(
        f"{BUDGET_BACKEND_URL}{path}",
        timeout=5,
    )

    response.raise_for_status()

    return response.json()


def get_budget_summary():
    """
    Return the current Budget Tracker summary.

    The result contains:
    - total budget
    - total spent
    - remaining budget
    - minimum price
    - maximum price
    """

    return _get("/api/budget/summary")


def get_budget_expenses():
    """
    Return all expense records from the Budget Tracker.
    """

    return _get("/api/expenses")