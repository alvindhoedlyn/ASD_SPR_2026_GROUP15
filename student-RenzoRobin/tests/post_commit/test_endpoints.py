"""Post-commit: tests for two endpoint functions of the Accommodation Recommender backend.

Endpoint 1: POST /recommendations  (ordering by priorities, city filter, database errors)
Endpoint 2: POST /multi-agent/run  (validation, feature flag, MCP evidence, service errors)

The database service, the MCP tool and the Multi-Agent Server are mocked, so these
tests run in CI without any other service.
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

pytestmark = pytest.mark.post_commit

_BACKEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "backend")
)


def _load_backend_app():
    # app.py does "from mcp_client import ...", so its folder must be on sys.path first.
    if _BACKEND_DIR not in sys.path:
        sys.path.insert(0, _BACKEND_DIR)
    spec = importlib.util.spec_from_file_location(
        "renzorobin_backend_app_post_commit", os.path.join(_BACKEND_DIR, "app.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def backend():
    return _load_backend_app()


@pytest.fixture
def client(backend):
    backend.app.config["TESTING"] = True
    with backend.app.test_client() as test_client:
        yield test_client


def make_response(json_body, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.side_effect = None
    return resp


# ============ Endpoint 1: POST /recommendations ============

PRICE_ONLY = {"price_weight": 100, "location_weight": 0, "facility_weight": 0, "review_weight": 0}
REVIEWS_ONLY = {"price_weight": 0, "location_weight": 0, "facility_weight": 0, "review_weight": 100}


def _accom(accom_id, name, city, price, rating=4, reviews=10):
    return {
        "accommodation_id": accom_id, "name": name, "city_area": city, "min_price": price,
        "facilities": [], "avg_rating": rating, "review_count": reviews,
    }


def _database_returns(backend, priorities, accoms):
    """The route asks the database service twice: user priorities, then the listings."""
    return patch.object(
        backend.requests, "request",
        side_effect=[make_response(priorities), make_response(accoms)],
    )


class TestRecommendationsEndpoint:
    def test_cheapest_listing_is_first_when_price_is_the_priority(self, client, backend):
        accoms = [_accom(1, "Pricey", "A", 200), _accom(2, "Cheap", "A", 20)]
        with _database_returns(backend, PRICE_ONLY, accoms):
            resp = client.post("/recommendations", json={"user_id": 1})

        assert resp.status_code == 200
        results = resp.get_json()["recommendations"]
        assert [r["name"] for r in results] == ["Cheap", "Pricey"]
        assert results[0]["score"] >= results[1]["score"]

    def test_user_priorities_change_the_order(self, client, backend):
        accoms = [
            _accom(1, "Well reviewed", "A", 100, rating=5, reviews=200),
            _accom(2, "Poorly reviewed", "A", 100, rating=2, reviews=5),
        ]
        with _database_returns(backend, REVIEWS_ONLY, accoms):
            resp = client.post("/recommendations", json={"user_id": 1})

        results = resp.get_json()["recommendations"]
        assert results[0]["name"] == "Well reviewed"

    def test_city_filter_only_returns_listings_in_that_city(self, client, backend):
        weights = {"price_weight": 50, "location_weight": 50, "facility_weight": 0, "review_weight": 0}
        accoms = [
            _accom(1, "In Bali", "Bali, Indonesia", 50),
            _accom(2, "In Kyoto", "Kyoto, Japan", 50),
        ]
        with _database_returns(backend, weights, accoms):
            resp = client.post("/recommendations", json={"user_id": 1, "city": "Bali, Indonesia"})

        results = resp.get_json()["recommendations"]
        assert [r["name"] for r in results] == ["In Bali"]

    def test_database_error_is_passed_back_to_the_caller(self, client, backend):
        failure = make_response({"error": "database service unavailable"}, 502)
        with patch.object(backend.requests, "request", return_value=failure):
            resp = client.post("/recommendations", json={"user_id": 1})

        assert resp.status_code == 502


# ============ Endpoint 2: POST /multi-agent/run ============

WORKFLOW = {"workflow_id": "abc123", "status": "pending_human_review", "degraded": False}


class TestMultiAgentRunEndpoint:
    def test_creates_a_workflow_from_mcp_evidence(self, client, backend):
        rows = [{"name": "Kyoto Zen Garden Inn", "facilities": ["wifi", "breakfast"]}]
        with patch.object(backend, "MULTI_AGENT_ENABLED", True), \
             patch.object(backend, "MCP_ENABLED", True), \
             patch.object(backend, "call_mcp_tool", return_value=rows) as mock_mcp, \
             patch.object(backend.requests, "request",
                          return_value=make_response(dict(WORKFLOW))) as mock_request:
            resp = client.post("/multi-agent/run", json={
                "question": "Which stays include breakfast?", "city_area": "Kyoto"})

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "pending_human_review"
        assert body["evidence_source"] == "mcp"
        mock_mcp.assert_called_once_with("accommodations_by_city", {"city_area": "Kyoto"})
        sent = mock_request.call_args.kwargs["json"]
        assert sent["user_request"] == "Which stays include breakfast?"
        assert sent["evidence"]["result"] == rows

    def test_still_creates_a_workflow_when_mcp_is_disabled(self, client, backend):
        with patch.object(backend, "MULTI_AGENT_ENABLED", True), \
             patch.object(backend, "MCP_ENABLED", False), \
             patch.object(backend.requests, "request",
                          return_value=make_response(dict(WORKFLOW))) as mock_request:
            resp = client.post("/multi-agent/run", json={"question": "Any cheap stays?"})

        assert resp.status_code == 200
        assert resp.get_json()["evidence_source"] == "none"
        assert mock_request.call_args.kwargs["json"]["evidence"] is None

    @pytest.mark.parametrize("body", [{}, {"question": 123}])
    def test_rejects_a_missing_or_non_text_question(self, client, backend, body):
        with patch.object(backend, "MULTI_AGENT_ENABLED", True), \
             patch.object(backend.requests, "request") as mock_request:
            resp = client.post("/multi-agent/run", json=body)

        assert resp.status_code == 400
        mock_request.assert_not_called()

    def test_is_blocked_when_multi_agent_mode_is_disabled(self, client, backend):
        with patch.object(backend, "MULTI_AGENT_ENABLED", False), \
             patch.object(backend.requests, "request") as mock_request:
            resp = client.post("/multi-agent/run", json={"question": "hello"})

        assert resp.status_code == 403
        assert resp.get_json()["error"] == "Multi-Agent mode is disabled"
        mock_request.assert_not_called()

    def test_reports_502_when_the_multi_agent_server_is_down(self, client, backend):
        down = requests.exceptions.ConnectionError("connection refused")
        with patch.object(backend, "MULTI_AGENT_ENABLED", True), \
             patch.object(backend, "MCP_ENABLED", False), \
             patch.object(backend.requests, "request", side_effect=down):
            resp = client.post("/multi-agent/run", json={"question": "hello"})

        assert resp.status_code == 502
        assert "unavailable" in resp.get_json()["error"]