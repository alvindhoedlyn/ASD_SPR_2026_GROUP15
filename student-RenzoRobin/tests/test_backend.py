import importlib.util
import os
import types
from unittest.mock import MagicMock, patch

import pytest
import requests

_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "app.py")


def _load_backend_app():
    spec = importlib.util.spec_from_file_location("renzorobin_backend_app", _APP_PATH)
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


# ===================== HEALTH =====================

class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["service"] == "backend-api"


# ===================== SCORING LOGIC (pure function, no mocking needed) =====================

class TestScoreAccommodation:
    def _sample_accoms(self):
        return [
            {"accommodation_id": 1, "min_price": 50, "city_area": "Bali, Indonesia",
             "facilities": ["wifi", "pool"], "avg_rating": 4.5, "review_count": 100},
            {"accommodation_id": 2, "min_price": 150, "city_area": "Kyoto, Japan",
             "facilities": ["wifi"], "avg_rating": 4.0, "review_count": 50},
        ]

    def test_cheaper_listing_scores_higher_on_price(self, backend):
        accoms = self._sample_accoms()
        weights = {"price_weight": 100, "location_weight": 0, "facility_weight": 0, "review_weight": 0}

        cheap_total, cheap_breakdown = backend.score_accommodation(accoms[0], weights, accoms, [], None)
        expensive_total, _ = backend.score_accommodation(accoms[1], weights, accoms, [], None)

        assert cheap_total > expensive_total
        assert cheap_breakdown["price_score"] == pytest.approx(1 - (50 / 150), abs=1e-3)

    def test_matching_city_scores_higher_on_location(self, backend):
        accoms = self._sample_accoms()
        weights = {"price_weight": 0, "location_weight": 100, "facility_weight": 0, "review_weight": 0}

        total, breakdown = backend.score_accommodation(accoms[0], weights, accoms, [], "Bali")
        assert breakdown["location_score"] == 1.0

        total_no_match, breakdown_no_match = backend.score_accommodation(accoms[1], weights, accoms, [], "Bali")
        assert breakdown_no_match["location_score"] == 0.4

    def test_facility_score_reflects_overlap_with_desired_facilities(self, backend):
        accoms = self._sample_accoms()
        weights = {"price_weight": 0, "location_weight": 0, "facility_weight": 100, "review_weight": 0}

        _, breakdown = backend.score_accommodation(
            accoms[0], weights, accoms, ["wifi", "pool", "breakfast"], None
        )
        # 2 of 3 desired facilities present
        assert breakdown["facility_score"] == pytest.approx(2 / 3, abs=1e-3)

    def test_facility_score_defaults_when_no_preference_given(self, backend):
        accoms = self._sample_accoms()
        weights = {"price_weight": 0, "location_weight": 0, "facility_weight": 100, "review_weight": 0}
        _, breakdown = backend.score_accommodation(accoms[0], weights, accoms, [], None)
        assert breakdown["facility_score"] == 0.5

    def test_zero_weights_do_not_raise_division_error(self, backend):
        accoms = self._sample_accoms()
        weights = {"price_weight": 0, "location_weight": 0, "facility_weight": 0, "review_weight": 0}
        total, _ = backend.score_accommodation(accoms[0], weights, accoms, [], None)
        assert total == 0

    def test_single_listing_does_not_raise_division_error(self, backend):
        # max_price / max_reviews come from a 1-item list — must not divide by zero
        solo = [{"accommodation_id": 1, "min_price": 0, "city_area": "Nowhere",
                 "facilities": [], "avg_rating": 0, "review_count": 0}]
        weights = {"price_weight": 25, "location_weight": 25, "facility_weight": 25, "review_weight": 25}
        total, breakdown = backend.score_accommodation(solo[0], weights, solo, [], None)
        assert isinstance(total, float)


# ===================== PROXY ROUTES =====================

class TestProxyRoutes:
    def test_list_areas_proxies_database_response(self, client, backend):
        with patch.object(backend.requests, "request", return_value=make_response(
            ["Bali, Indonesia", "Kyoto, Japan"]
        )):
            resp = client.get("/areas")
        assert resp.status_code == 200
        assert resp.get_json() == ["Bali, Indonesia", "Kyoto, Japan"]

    def test_database_unavailable_returns_502(self, client, backend):
        with patch.object(
            backend.requests, "request",
            side_effect=requests.exceptions.ConnectionError("connection refused"),
        ):
            resp = client.get("/areas")
        assert resp.status_code == 502
        assert "error" in resp.get_json()

    def test_get_accommodation_proxies_with_id(self, client, backend):
        with patch.object(backend.requests, "request", return_value=make_response(
            {"accommodation_id": 5, "name": "Test Villa"}
        )) as mock_request:
            resp = client.get("/accommodations/5")
        assert resp.status_code == 200
        assert resp.get_json()["accommodation_id"] == 5
        called_url = mock_request.call_args.args[1]
        assert called_url.endswith("/accommodations/5")

    def test_create_accommodation_forwards_post_body(self, client, backend):
        payload = {"name": "New Place", "city_area": "Testville"}
        with patch.object(backend.requests, "request", return_value=make_response(
            {"accommodation_id": 99}, 201
        )) as mock_request:
            resp = client.post("/accommodations", json=payload)
        assert resp.status_code == 201
        assert mock_request.call_args.kwargs["json"] == payload

    def test_not_found_from_database_passes_through_as_404(self, client, backend):
        with patch.object(backend.requests, "request", return_value=make_response(
            {"error": "not found"}, 404
        )):
            resp = client.get("/accommodations/99999")
        assert resp.status_code == 404


# ===================== RECOMMENDATIONS =====================

class TestRecommendations:
    def _mock_db_sequence(self, backend, priorities, accoms):
        """First call returns priorities, second returns accommodations-with-price."""
        responses = [make_response(priorities), make_response(accoms)]
        return patch.object(backend.requests, "request", side_effect=responses)

    def test_recommendations_are_sorted_best_match_first(self, client, backend):
        priorities = {"price_weight": 100, "location_weight": 0, "facility_weight": 0, "review_weight": 0}
        accoms = [
            {"accommodation_id": 1, "name": "Pricey", "city_area": "A", "min_price": 200,
             "facilities": [], "avg_rating": 4, "review_count": 10},
            {"accommodation_id": 2, "name": "Cheap", "city_area": "A", "min_price": 20,
             "facilities": [], "avg_rating": 4, "review_count": 10},
        ]
        with self._mock_db_sequence(backend, priorities, accoms):
            resp = client.post("/recommendations", json={"user_id": 1})

        assert resp.status_code == 200
        results = resp.get_json()["recommendations"]
        assert results[0]["name"] == "Cheap"
        assert results[0]["score"] >= results[1]["score"]

    def test_recommendations_filters_by_city(self, client, backend):
        priorities = {"price_weight": 50, "location_weight": 50, "facility_weight": 0, "review_weight": 0}
        accoms = [
            {"accommodation_id": 1, "name": "In Bali", "city_area": "Bali, Indonesia", "min_price": 50,
             "facilities": [], "avg_rating": 4, "review_count": 10},
            {"accommodation_id": 2, "name": "In Kyoto", "city_area": "Kyoto, Japan", "min_price": 50,
             "facilities": [], "avg_rating": 4, "review_count": 10},
        ]
        with self._mock_db_sequence(backend, priorities, accoms):
            resp = client.post("/recommendations", json={"user_id": 1, "city": "Bali, Indonesia"})

        results = resp.get_json()["recommendations"]
        assert len(results) == 1
        assert results[0]["name"] == "In Bali"

    def test_recommendations_propagates_db_error(self, client, backend):
        with patch.object(backend.requests, "request", return_value=make_response(
            {"error": "database service unavailable"}, 502
        )):
            resp = client.post("/recommendations", json={"user_id": 1})
        assert resp.status_code == 502


# ===================== SIMILARITY =====================

class TestSimilarityMatch:
    def test_similar_excludes_the_target_and_limits_to_four(self, client, backend):
        accoms = [
            {"accommodation_id": i, "name": f"Listing {i}", "city_area": "Bali, Indonesia",
             "min_price": 50 + i, "facilities": ["wifi"]}
            for i in range(1, 7)
        ]
        with patch.object(backend.requests, "request", return_value=make_response(accoms)):
            resp = client.get("/accommodations/1/similar")

        assert resp.status_code == 200
        results = resp.get_json()
        assert len(results) == 4
        assert all(r["accommodation_id"] != 1 for r in results)

    def test_similar_returns_404_for_unknown_target(self, client, backend):
        accoms = [{"accommodation_id": 1, "name": "Only One", "city_area": "A",
                   "min_price": 50, "facilities": []}]
        with patch.object(backend.requests, "request", return_value=make_response(accoms)):
            resp = client.get("/accommodations/999/similar")
        assert resp.status_code == 404


# ===================== AI EXPLAIN ENDPOINTS =====================

class TestExplainEndpoints:
    def _mock_ai_response(self, text):
        message = types.SimpleNamespace(content=text)
        choice = types.SimpleNamespace(message=message)
        return types.SimpleNamespace(choices=[choice])

    def test_explain_returns_ai_text_on_success(self, client, backend):
        fake_response = self._mock_ai_response("A lovely villa with a great pool.")
        with patch.object(backend.client.chat.completions, "create", return_value=fake_response):
            resp = client.post("/recommendations/explain", json={
                "name": "Test Villa", "city_area": "Bali", "starting_price": 50,
                "avg_rating": 4.8, "review_count": 100, "facilities": ["wifi", "pool"], "score": 0.9,
            })
        assert resp.status_code == 200
        assert "villa" in resp.get_json()["explanation"].lower()

    def test_explain_returns_503_when_ai_unreachable(self, client, backend):
        with patch.object(
            backend.client.chat.completions, "create",
            side_effect=Exception("connection refused"),
        ):
            resp = client.post("/recommendations/explain", json={"name": "Test Villa"})
        assert resp.status_code == 503
        assert "error" in resp.get_json()

    def test_explain_compare_requires_items(self, client):
        resp = client.post("/recommendations/explain-compare", json={"items": []})
        assert resp.status_code == 400

    def test_explain_compare_names_the_winner(self, client, backend):
        fake_response = self._mock_ai_response("Villa A is the best match.")
        with patch.object(backend.client.chat.completions, "create", return_value=fake_response) as mock_create:
            resp = client.post("/recommendations/explain-compare", json={
                "items": [
                    {"name": "Villa A", "starting_price": 50, "city_area": "Bali",
                     "avg_rating": 4.8, "review_count": 100, "facilities": ["wifi"], "score": 0.9},
                    {"name": "Villa B", "starting_price": 200, "city_area": "Kyoto",
                     "avg_rating": 3.5, "review_count": 10, "facilities": [], "score": 0.4},
                ]
            })
        assert resp.status_code == 200
        # The prompt sent to the AI should name the actual highest-scoring option
        sent_prompt = mock_create.call_args.kwargs["messages"][1]["content"]
        assert "Villa A" in sent_prompt
        assert "90%" in sent_prompt