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

AUTH_HEADERS = {
    "Authorization": "Bearer test-session-token"
}


def verified_session_response(user_id=7):
    return FakeResponse({
        "user_id": user_id,
        "username": "test-user",
        "role": "client"
    })


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
            "attraction_id": 1,
            "attraction_name": "Test Nature Garden",
            "notes": "Morning visit"
        }
    ]

    def fake_get(url, params, timeout):
        if url.endswith("/api/verify-session"):
            assert params == {"token": "test-session-token"}
            return verified_session_response()

        assert url.endswith("/saved-places")
        assert params == {"user_id": 7}
        return FakeResponse(saved_places)

    with patch.object(
        backend_app.requests,
        "get",
        side_effect=fake_get
    ):
        response = client.get(
            "/api/saved-places",
            headers=AUTH_HEADERS
        )

    assert response.status_code == 200
    assert response.get_json() == saved_places

def test_save_attraction(client):
    with (
        patch.object(
            backend_app.requests,
            "get",
            return_value=verified_session_response()
        ),
        patch.object(
            backend_app.requests,
            "post",
            return_value=FakeResponse(
                {
                    "message": "Place saved successfully",
                    "saved_place_id": 20
                },
                201
            )
        ) as mock_post
    ):
        response = client.post(
            "/api/saved-places",
            headers=AUTH_HEADERS,
            json={
                "attraction_id": 1,
                "notes": "Morning visit",
                "user_id": 999
            }
        )

    response_data = response.get_json()

    assert response.status_code == 201
    assert response_data["saved_place_id"] == 20
    assert mock_post.call_args.kwargs["json"] == {
        "user_id": 7,
        "attraction_id": 1,
        "notes": "Morning visit"
    }


def test_save_attraction_requires_attraction_id(client):
    with patch.object(
        backend_app.requests,
        "get",
        return_value=verified_session_response()
    ):
        response = client.post(
            "/api/saved-places",
            headers=AUTH_HEADERS,
            json={"notes": "Morning visit"}
        )

    assert response.status_code == 400
    assert response.get_json()["fields"] == ["attraction_id"]


def test_update_saved_attraction(client):
    with (
        patch.object(
            backend_app.requests,
            "get",
            return_value=verified_session_response()
        ),
        patch.object(
            backend_app.requests,
            "put",
            return_value=FakeResponse({
                "message": "Saved place updated successfully",
                "saved_place_id": 20
            })
        ) as mock_put
    ):
        response = client.put(
            "/api/saved-places/20",
            headers=AUTH_HEADERS,
            json={
                "notes": "Visit in the afternoon"
            }
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["saved_place_id"] == 20
    assert mock_put.call_args.kwargs["json"] == {
        "user_id": 7,
        "notes": "Visit in the afternoon"
    }


def test_delete_saved_attraction(client):
    with (
        patch.object(
            backend_app.requests,
            "get",
            return_value=verified_session_response()
        ),
        patch.object(
            backend_app.requests,
            "delete",
            return_value=FakeResponse({
                "message": "Saved place deleted successfully",
                "saved_place_id": 20
            })
        ) as mock_delete
    ):
        response = client.delete(
            "/api/saved-places/20",
            headers=AUTH_HEADERS
        )

    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["saved_place_id"] == 20
    assert mock_delete.call_args.kwargs["params"] == {
        "user_id": 7
    }


def test_saved_places_require_authentication(client):
    response = client.get("/api/saved-places")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Authentication required"


def test_saved_places_reject_invalid_session(client):
    with patch.object(
        backend_app.requests,
        "get",
        return_value=FakeResponse(
            {"error": "Invalid or expired session"},
            401
        )
    ):
        response = client.get(
            "/api/saved-places",
            headers={"Authorization": "Bearer expired-token"}
        )

    assert response.status_code == 401
    assert response.get_json()["error"] == (
        "Invalid or expired session"
    )

def test_release_one_status_when_services_are_disabled(client):
    with (
        patch.object(backend_app, "MCP_ENABLED", False),
        patch.object(backend_app, "RAG_ENABLED", False),
        patch.object(backend_app, "MCP_SERVER_URL", ""),
        patch.object(backend_app, "RAG_SERVER_URL", "")
    ):
        response = client.get("/api/release-1/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "mcp": {
            "enabled": False,
            "configured": False
        },
        "rag": {
            "enabled": False,
            "configured": False
        }
    }


def test_release_one_status_when_services_are_configured(client):
    with (
        patch.object(backend_app, "MCP_ENABLED", True),
        patch.object(backend_app, "RAG_ENABLED", True),
        patch.object(
            backend_app,
            "MCP_SERVER_URL",
            "http://example-mcp"
        ),
        patch.object(
            backend_app,
            "RAG_SERVER_URL",
            "http://example-rag"
        )
    ):
        response = client.get("/api/release-1/status")

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["mcp"] == {
        "enabled": True,
        "configured": True
    }
    assert response_data["rag"] == {
        "enabled": True,
        "configured": True
    }

def test_rag_answer_is_disabled_during_ci(client):
    with (
        patch.object(backend_app, "RAG_ENABLED", False),
        patch.object(
            backend_app.requests,
            "post"
        ) as mock_post
    ):
        response = client.post(
            "/api/rag/answer",
            json={"query": "Which attractions are free?"}
        )

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "RAG mode is disabled"
    )
    mock_post.assert_not_called()


def test_rag_answer_requires_query(client):
    with patch.object(
        backend_app,
        "RAG_ENABLED",
        True
    ):
        response = client.post(
            "/api/rag/answer",
            json={}
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "query is required"


def test_rag_answer_returns_grounded_response(client):
    rag_result = {
        "status": "success",
        "query": "Which Sydney attractions are free?",
        "answer": (
            "The Royal Botanic Garden and Bondi Beach "
            "have an estimated cost of 0 AUD."
        ),
        "citations": [
            {
                "chunk_id": "location_2",
                "source_id": (
                    "student-TrongDao-database:/places/2"
                ),
                "authority_tier": "tier_1"
            }
        ],
        "confidence_category": "High",
        "retrieval_summary": {
            "k": 5,
            "retrieved_count": 5,
            "top_chunk": "location_2"
        }
    }

    with (
        patch.object(backend_app, "RAG_ENABLED", True),
        patch.object(
            backend_app,
            "RAG_SERVER_URL",
            "http://rag-server.test"
        ),
        patch.object(
            backend_app.requests,
            "post",
            return_value=FakeResponse(rag_result)
        ) as mock_post
    ):
        response = client.post(
            "/api/rag/answer",
            json={
                "query": "Which Sydney attractions are free?",
                "k": 5
            }
        )

    assert response.status_code == 200
    assert response.get_json() == rag_result

    mock_post.assert_called_once_with(
        "http://rag-server.test/answer",
        json={
            "query": "Which Sydney attractions are free?",
            "k": 5,
            "caller": "student-TrongDao"
        },
        timeout=backend_app.RAG_REQUEST_TIMEOUT
    )


def test_rag_answer_preserves_insufficient_context(client):
    rag_result = {
        "status": "insufficient_context",
        "query": "Which attractions are open on Mars?",
        "answer": (
            "Insufficient context available to answer "
            "this question."
        ),
        "citations": [],
        "confidence_category": "Insufficient",
        "retrieval_summary": {
            "k": 5,
            "retrieved_count": 5
        }
    }

    with (
        patch.object(backend_app, "RAG_ENABLED", True),
        patch.object(
            backend_app,
            "RAG_SERVER_URL",
            "http://rag-server.test"
        ),
        patch.object(
            backend_app.requests,
            "post",
            return_value=FakeResponse(rag_result)
        )
    ):
        response = client.post(
            "/api/rag/answer",
            json={
                "query": "Which attractions are open on Mars?"
            }
        )

    assert response.status_code == 200
    assert response.get_json()["status"] == (
        "insufficient_context"
    )
    assert response.get_json()["citations"] == []
    assert response.get_json()["confidence_category"] == (
        "Insufficient"
    )