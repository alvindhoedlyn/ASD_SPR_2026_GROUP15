import sys
from pathlib import Path
from unittest.mock import patch

import pytest


BACKEND_DIRECTORY = (
    Path(__file__).resolve().parents[2] / "backend"
)

sys.path.insert(0, str(BACKEND_DIRECTORY))

import app as backend_app


EVIDENCE = [
    {
        "name": "Royal Botanic Garden",
        "attraction_id": 2,
        "city": "Sydney",
        "country": "Australia",
        "category": "nature",
        "estimated_cost": 0,
        "currency": "AUD"
    }
]


@pytest.fixture
def client():
    backend_app.app.config["TESTING"] = True

    with backend_app.app.test_client() as test_client:
        yield test_client


def test_run_multi_agent_workflow_endpoint(client):
    workflow_result = {
        "workflow_id": "workflow-123",
        "status": "pending_human_review",
        "evidence_count": 1,
        "steps": {
            "planner": {
                "status": "completed"
            },
            "worker": {
                "status": "completed"
            },
            "reviewer": {
                "status": "completed"
            }
        },
        "human_decision": {
            "status": "pending"
        }
    }

    with (
        patch.object(
            backend_app,
            "MULTI_AGENT_ENABLED",
            True
        ),
        patch.object(
            backend_app,
            "collect_attraction_evidence",
            return_value=(EVIDENCE, None)
        ) as evidence_mock,
        patch.object(
            backend_app,
            "call_multi_agent_service",
            return_value=(workflow_result, 200)
        ) as service_mock
    ):
        response = client.post(
            "/api/multi-agent/run",
            json={
                "question": (
                    "Which Sydney nature attractions "
                    "are free?"
                ),
                "city": "Sydney",
                "category": "nature"
            },
            headers={
                "X-Multi-Agent-Mode": "on"
            }
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["workflow_id"] == "workflow-123"
    assert (
        response_data["status"]
        == "pending_human_review"
    )
    assert (
        response_data["evidence_source"]
        == "location-database"
    )
    assert response_data["evidence_city"] == "Sydney"
    assert response_data["evidence_category"] == "nature"

    evidence_mock.assert_called_once_with(
        "Sydney",
        "nature"
    )

    service_mock.assert_called_once_with(
        "POST",
        "/workflow",
        {
            "user_request": (
                "Which Sydney nature attractions "
                "are free?"
            ),
            "feature": "location-recommender",
            "evidence": EVIDENCE,
            "caller": "student-4"
        }
    )


def test_record_human_decision_endpoint(client):
    decision_result = {
        "workflow_id": "workflow-123",
        "status": "accepted",
        "human_decision": {
            "status": "accepted",
            "decision": "accept",
            "note": "Evidence matches the database."
        }
    }

    with (
        patch.object(
            backend_app,
            "MULTI_AGENT_ENABLED",
            True
        ),
        patch.object(
            backend_app,
            "call_multi_agent_service",
            return_value=(decision_result, 200)
        ) as service_mock
    ):
        response = client.post(
            (
                "/api/multi-agent/"
                "workflow-123/decision"
            ),
            json={
                "decision": "accept",
                "note": "Evidence matches the database."
            },
            headers={
                "X-Multi-Agent-Mode": "on"
            }
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["status"] == "accepted"
    assert (
        response_data["human_decision"]["decision"]
        == "accept"
    )

    service_mock.assert_called_once_with(
        "POST",
        "/workflow/workflow-123/decision",
        {
            "decision": "accept",
            "note": "Evidence matches the database.",
            "corrected_output": ""
        }
    )