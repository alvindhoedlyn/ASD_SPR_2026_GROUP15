import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests


BACKEND_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "backend"
)

sys.path.insert(0, str(BACKEND_DIRECTORY))

import app as backend_app


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
        self.ok = 200 <= status_code < 300

    def json(self):
        return self.data

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(
                f"HTTP status {self.status_code}"
            )


SAMPLE_PLACES = [
    {
        "attraction_id": 1,
        "attraction_name": "Test Nature Garden",
        "city": "Sydney",
        "country": "Australia",
        "category": "nature",
        "longitude": 151.20,
        "latitude": -33.86,
        "estimated_cost": 0,
        "currency": "AUD",
        "expected_duration_minutes": 120,
        "indoor_outdoor": "outdoor",
        "crowd_level": "low",
        "beginner_friendliness_score": 5,
        "accessibility_information": "Accessible paths",
        "attraction_description": "A quiet public garden."
    },
    {
        "attraction_id": 2,
        "attraction_name": "Test Art Museum",
        "city": "Sydney",
        "country": "Australia",
        "category": "art",
        "longitude": 151.21,
        "latitude": -33.87,
        "estimated_cost": 20,
        "currency": "AUD",
        "expected_duration_minutes": 90,
        "indoor_outdoor": "indoor",
        "crowd_level": "medium",
        "beginner_friendliness_score": 3,
        "accessibility_information": "Accessible entrance",
        "attraction_description": "A small art collection."
    }
]


def recommendation_request(ai_mode=False):
    return {
        "journey_id": "PYTEST-01",
        "destination_city": "Sydney",
        "arrival_date": "2026-09-10",
        "departure_date": "2026-09-15",
        "interests": ["nature"],
        "weather_preferences": "outdoor",
        "crowd_tolerance": "medium",
        "budget_range": "low",
        "accessibility_needs": "None",
        "ai_mode": ai_mode
    }


@pytest.fixture
def client():
    backend_app.app.config["TESTING"] = True

    with backend_app.app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_missing_recommendation_fields(client):
    response = client.post(
        "/api/recommendations",
        json={
            "journey_id": "PYTEST-01"
        }
    )

    response_data = response.get_json()

    assert response.status_code == 400
    assert response_data["error"] == "Missing required fields"
    assert "destination_city" in response_data["fields"]


def test_deterministic_recommendations(client):
    def fake_get(url, timeout):
        assert url.endswith("/places")
        return FakeResponse(SAMPLE_PLACES)

    def fake_post(url, json, timeout):
        assert url.endswith("/recommendation-requests")

        return FakeResponse(
            {
                "message": (
                    "Recommendation request added successfully"
                ),
                "request_id": 101
            },
            201
        )

    with (
        patch.object(
            backend_app.requests,
            "get",
            side_effect=fake_get
        ),
        patch.object(
            backend_app.requests,
            "post",
            side_effect=fake_post
        )
    ):
        response = client.post(
            "/api/recommendations",
            json=recommendation_request(ai_mode=False)
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["mode"] == "data"
    assert response_data["request_id"] == 101
    assert response_data["ai_explanation"] is None
    assert response_data["agentic_workflow"] == []

    assert response_data["recommendation_count"] == 2

    first_place = response_data["recommendations"][0]

    assert first_place["attraction_id"] == 1
    assert first_place["attraction_name"] == (
        "Test Nature Garden"
    )
    assert first_place["recommendation_score"] > (
        response_data["recommendations"][1][
            "recommendation_score"
        ]
    )


def test_ai_recommendations_and_review(client):
    def fake_get(url, timeout):
        return FakeResponse(SAMPLE_PLACES)

    def fake_post(url, json, timeout):
        if url.endswith("/api/chat"):
            if json["model"] == "qwen2.5:0.5b":
                return FakeResponse({
                    "message": {
                        "content": "Qwen recommendation draft"
                    }
                })

            if json["model"] == "llama3.1:8b":
                return FakeResponse({
                    "message": {
                        "content": "Llama reviewed explanation"
                    }
                })

        if url.endswith("/recommendation-requests"):
            return FakeResponse(
                {
                    "message": (
                        "Recommendation request added successfully"
                    ),
                    "request_id": 102
                },
                201
            )

        raise AssertionError(f"Unexpected URL: {url}")

    with (
        patch.object(
            backend_app.requests,
            "get",
            side_effect=fake_get
        ),
        patch.object(
            backend_app.requests,
            "post",
            side_effect=fake_post
        )
    ):
        response = client.post(
            "/api/recommendations",
            json=recommendation_request(ai_mode=True)
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["mode"] == "ai"
    assert response_data["implementation_model"] == (
        "qwen2.5:0.5b"
    )
    assert response_data["review_model"] == "llama3.1:8b"
    assert response_data["ai_draft"] == (
        "Qwen recommendation draft"
    )
    assert response_data["ai_review"] == (
        "Llama reviewed explanation"
    )
    assert response_data["ai_explanation"] == (
        "Llama reviewed explanation"
    )
    assert response_data["ai_error"] is None
    assert response_data["review_error"] is None

    phases = [
        step["phase"]
        for step in response_data["agentic_workflow"]
    ]

    assert phases == [
        "PLAN",
        "ACT",
        "OBSERVE",
        "REVIEW",
        "ADAPT"
    ]


def test_ai_fallback_when_ollama_is_unavailable(client):
    def fake_get(url, timeout):
        return FakeResponse(SAMPLE_PLACES)

    def fake_post(url, json, timeout):
        if url.endswith("/api/chat"):
            raise requests.ConnectionError(
                "Ollama unavailable"
            )

        if url.endswith("/recommendation-requests"):
            return FakeResponse(
                {
                    "message": (
                        "Recommendation request added successfully"
                    ),
                    "request_id": 103
                },
                201
            )

        raise AssertionError(f"Unexpected URL: {url}")

    with (
        patch.object(
            backend_app.requests,
            "get",
            side_effect=fake_get
        ),
        patch.object(
            backend_app.requests,
            "post",
            side_effect=fake_post
        )
    ):
        response = client.post(
            "/api/recommendations",
            json=recommendation_request(ai_mode=True)
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["recommendation_count"] == 2
    assert response_data["ai_draft"] is None
    assert response_data["ai_review"] is None
    assert response_data["ai_explanation"] is None
    assert response_data["ai_error"] is not None

    phases = [
        step["phase"]
        for step in response_data["agentic_workflow"]
    ]

    assert phases == [
        "PLAN",
        "ACT",
        "OBSERVE",
        "ADAPT"
    ]


def test_get_saved_places(client):
    saved_places = [
        {
            "saved_place_id": 1,
            "journey_id": "PYTEST-01",
            "attraction_id": 1,
            "attraction_name": "Test Nature Garden",
            "notes": "Morning visit"
        }
    ]

    with patch.object(
        backend_app.requests,
        "get",
        return_value=FakeResponse(saved_places)
    ) as mock_get:
        response = client.get(
            "/api/saved-places?journey_id=PYTEST-01"
        )

    assert response.status_code == 200
    assert response.get_json() == saved_places

    mock_get.assert_called_once_with(
        f"{backend_app.DATABASE_API_URL}/saved-places",
        params={"journey_id": "PYTEST-01"},
        timeout=5
    )


def test_save_attraction(client):
    with patch.object(
        backend_app.requests,
        "post",
        return_value=FakeResponse(
            {
                "message": "Place saved successfully",
                "saved_place_id": 20
            },
            201
        )
    ):
        response = client.post(
            "/api/saved-places",
            json={
                "journey_id": "PYTEST-01",
                "attraction_id": 1,
                "notes": "Morning visit"
            }
        )

    response_data = response.get_json()

    assert response.status_code == 201
    assert response_data["saved_place_id"] == 20


def test_update_saved_attraction(client):
    with patch.object(
        backend_app.requests,
        "put",
        return_value=FakeResponse({
            "message": "Saved place updated successfully",
            "saved_place_id": 20
        })
    ):
        response = client.put(
            "/api/saved-places/20",
            json={
                "journey_id": "PYTEST-01",
                "attraction_id": 1,
                "notes": "Visit in the afternoon"
            }
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["saved_place_id"] == 20


def test_delete_saved_attraction(client):
    with patch.object(
        backend_app.requests,
        "delete",
        return_value=FakeResponse({
            "message": "Saved place deleted successfully",
            "saved_place_id": 20
        })
    ):
        response = client.delete("/api/saved-places/20")

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["saved_place_id"] == 20