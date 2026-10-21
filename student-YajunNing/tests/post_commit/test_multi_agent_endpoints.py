"""Student 5 post-commit tests for exactly two backend endpoint functions.

Endpoint 1: POST /api/multi-agent/run
Endpoint 2: POST /api/multi-agent/<workflow_id>/decision
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.post_commit
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

import app as backend_app


@pytest.fixture
def client():
    backend_app.app.config["TESTING"] = True
    with backend_app.app.test_client() as test_client:
        yield test_client


def database_response(records):
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = records
    return response


def test_run_multi_agent_workflow_endpoint(client):
    evidence = [
        {
            "id": 4,
            "airline": "Qantas",
            "flight_number": "QF25",
            "origin": "SYD",
            "destination": "HND",
            "price_aud": 890,
            "duration_minutes": 575,
            "stops": 0,
        }
    ]
    workflow = {
        "workflow_id": "flight-review-123",
        "status": "pending_human_review",
        "evidence_count": 1,
        "steps": {
            "planner": {"status": "ok"},
            "worker": {"status": "ok"},
            "reviewer": {"status": "ok"},
        },
        "human_decision": {"status": "pending"},
    }

    with (
        patch.object(backend_app, "MULTI_AGENT_ENABLED", True),
        patch.object(
            backend_app,
            "database_request",
            return_value=database_response(evidence),
        ) as database_mock,
        patch.object(
            backend_app,
            "call_multi_agent_service",
            return_value=(workflow, 200),
        ) as service_mock,
    ):
        response = client.post(
            "/api/multi-agent/run",
            json={"question": "Which direct flight is within budget?", "max_budget": 900},
            headers={"X-Multi-Agent-Mode": "on"},
        )

    body = response.get_json()
    assert response.status_code == 200
    assert body["status"] == "pending_human_review"
    assert body["evidence_source"] == "flight-database"
    database_mock.assert_called_once_with("GET", "/flights", params={"max_budget": 900.0})
    service_mock.assert_called_once_with(
        "POST",
        "/workflow",
        {
            "user_request": "Which direct flight is within budget?",
            "feature": "flight-recommender",
            "evidence": evidence,
            "caller": "student-5",
        },
    )


def test_record_human_decision_endpoint(client):
    decision = {
        "workflow_id": "flight-review-123",
        "status": "accepted",
        "human_decision": {
            "status": "accepted",
            "decision": "accept",
            "note": "The recommendation matches the catalogue evidence.",
        },
    }
    with (
        patch.object(backend_app, "MULTI_AGENT_ENABLED", True),
        patch.object(
            backend_app,
            "call_multi_agent_service",
            return_value=(decision, 200),
        ) as service_mock,
    ):
        response = client.post(
            "/api/multi-agent/flight-review-123/decision",
            json={
                "decision": "accept",
                "note": "The recommendation matches the catalogue evidence.",
            },
            headers={"X-Multi-Agent-Mode": "on"},
        )

    assert response.status_code == 200
    assert response.get_json()["human_decision"]["decision"] == "accept"
    service_mock.assert_called_once_with(
        "POST",
        "/workflow/flight-review-123/decision",
        {
            "decision": "accept",
            "note": "The recommendation matches the catalogue evidence.",
            "corrected_output": "",
        },
    )
