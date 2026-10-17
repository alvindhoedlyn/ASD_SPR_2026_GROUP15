"""Post-commit: access control, input validation and injection checks for the
backend API (backend/app.py) and the database service (database/init_db.py)."""

import pytest
from helpers import FakeResponse

pytestmark = pytest.mark.post_commit

PROTECTED_ROUTES = [
    ("GET", "/api/trips"),
    ("POST", "/api/trips/generate"),
    ("PUT", "/api/trips/1/regenerate"),
    ("PUT", "/api/trips/1/days/1"),
    ("DELETE", "/api/trips/1/days/1"),
    ("DELETE", "/api/trips/1"),
    ("POST", "/mcp/generate-trip-itinerary"),
    ("POST", "/rag/refresh"),
    ("POST", "/rag/retrieve"),
    ("POST", "/rag/activities"),
]

OWNERSHIP_ROUTES = [
    ("PUT", "/api/trips/2/regenerate"),
    ("PUT", "/api/trips/2/days/1"),
    ("DELETE", "/api/trips/2/days/1"),
    ("DELETE", "/api/trips/2"),
]


# ----------------------------- backend: auth -----------------------------

def test_health_is_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


@pytest.mark.parametrize(("method", "path"), PROTECTED_ROUTES)
def test_protected_routes_require_a_session(client, services, method, path):
    resp = client.open(path, method=method, json={})
    assert resp.status_code == 401
    assert not services.writes(), "an unauthenticated request reached the database service"


# --------------------------- backend: ownership ---------------------------

@pytest.mark.parametrize(("method", "path"), OWNERSHIP_ROUTES)
def test_cannot_modify_another_users_trip(client, services, auth, method, path):
    resp = client.open(path, method=method, headers=auth(user_id=1), json={})
    assert resp.status_code == 403
    assert not services.writes(), "a forbidden request still modified data"


@pytest.mark.parametrize(("method", "path"), [
    ("DELETE", "/api/trips/999"),
    ("PUT", "/api/trips/999/regenerate"),
    ("PUT", "/api/trips/999/days/1"),
    ("DELETE", "/api/trips/999/days/1"),
])
def test_unknown_trip_is_404(client, auth, method, path):
    assert client.open(path, method=method, headers=auth(1), json={}).status_code == 404


@pytest.mark.parametrize(("user_id", "expected_trip_ids"), [(1, [1]), (2, [2]), (3, [])])
def test_trip_list_only_contains_the_callers_trips(client, auth, user_id, expected_trip_ids):
    resp = client.get("/api/trips", headers=auth(user_id))
    assert resp.status_code == 200
    assert [t["trip_id"] for t in resp.get_json()] == expected_trip_ids


def test_client_supplied_user_id_is_ignored(client, services, auth):
    body = {"journeyId": 1, "duration": 2, "userId": 2, "user_id": 2}
    resp = client.post("/api/trips/generate", headers=auth(user_id=1), json=body)
    assert resp.status_code == 201
    assert services.created_payload["user_id"] == 1
    assert resp.get_json()["user_id"] == 1


# --------------------------- backend: validation ---------------------------

@pytest.mark.parametrize("body", [
    {"journeyId": 1, "duration": 0},
    {"journeyId": 1, "duration": 15},
    {"journeyId": 1, "duration": -3},
    {"journeyId": 1, "duration": "abc"},
    {"journeyId": 0, "duration": 3},
    {"journeyId": None, "duration": 3},
    {},
])
def test_generate_rejects_bad_input(client, services, auth, body):
    resp = client.post("/api/trips/generate", headers=auth(1), json=body)
    assert resp.status_code == 400
    assert services.created_payload is None


def test_generate_unknown_journey_is_404(client, auth):
    resp = client.post("/api/trips/generate", headers=auth(1), json={"journeyId": 7, "duration": 2})
    assert resp.status_code == 404


def test_generate_happy_path(client, services, auth):
    resp = client.post(
        "/api/trips/generate", headers=auth(1), json={"journeyId": 1, "duration": 3}
    )
    assert resp.status_code == 201
    assert len(resp.get_json()["days"]) == 3


def test_rag_retrieve_requires_a_query(client, auth):
    assert client.post("/rag/retrieve", headers=auth(1), json={"query": "  "}).status_code == 400


def test_rag_retrieve_rejects_non_numeric_k(client, auth):
    resp = client.post("/rag/retrieve", headers=auth(1), json={"query": "beach", "k": "lots"})
    assert resp.status_code == 400


def test_ask_with_context_requires_a_question(client):
    assert client.post("/ask-with-context", json={"question": "  "}).status_code == 400


# ------------------------- backend: feature switches -------------------------

def test_rag_mode_header_off_blocks_rag_routes(client, auth):
    resp = client.post("/rag/refresh", headers={**auth(1), "X-RAG-Mode": "off"})
    assert resp.status_code == 403


def test_mcp_mode_header_off_blocks_mcp_routes(client, auth):
    resp = client.get("/mcp/tools", headers={**auth(1), "X-MCP-Mode": "off"})
    assert resp.status_code == 403


# ---------------------- backend: known weaknesses (xfail) ----------------------

@pytest.mark.xfail(reason="Known gap: LLM output is returned as raw HTML (XSS).", strict=False)
def test_ask_with_context_escapes_model_output(client, backend_module, monkeypatch):
    payload = "<script>alert(1)</script>"
    completion = type("C", (), {"choices": [type("Ch", (), {"message": type("M", (), {"content": payload})()})()]})()
    monkeypatch.setattr(backend_module.client.chat.completions, "create", lambda *a, **k: completion)

    resp = client.post("/ask-with-context", json={"question": "hi", "itinerary": "x"})
    assert payload not in resp.get_data(as_text=True)


@pytest.mark.xfail(reason="Known gap: CORS reflects any Origin (origins='*').", strict=False)
def test_cors_does_not_allow_arbitrary_origins(client):
    # flask-cors echoes the caller's Origin when configured with "*", so check both forms.
    resp = client.get("/health", headers={"Origin": "https://evil.example"})
    assert resp.headers.get("Access-Control-Allow-Origin") not in ("*", "https://evil.example")


# ----------------------------- database service -----------------------------

def test_db_unknown_trip_is_404(db_client):
    assert db_client.get("/api/trips/9999/details").status_code == 404
    assert db_client.delete("/api/trips/9999").status_code == 404


def test_db_seed_data_is_present(db_client):
    assert len(db_client.get("/api/journeys").get_json()) == 10
    assert db_client.get("/api/journeys/9999").status_code == 404


def test_db_sql_injection_payload_is_stored_as_plain_text(db_client):
    evil = "x'); DROP TABLE trip; --"
    day = {"day_number": 1, "location": "L", "weather": evil, "itinerary": evil, "activity": evil}
    resp = db_client.post(
        "/api/trips", json={"user_id": 1, "journey_id": 1, "duration": 1, "days": [day]}
    )
    assert resp.status_code == 201
    trip_id = resp.get_json()["trip_id"]

    # Tables survived and the value round-trips unchanged.
    assert db_client.get("/api/trips").status_code == 200
    stored = db_client.get(f"/api/trips/{trip_id}/days").get_json()
    assert stored[0]["weather"] == evil


def test_db_route_params_must_be_integers(db_client):
    assert db_client.get("/api/trips/1;DROP TABLE trip/details").status_code == 404
    assert db_client.delete("/api/trips/abc").status_code == 404


@pytest.mark.xfail(reason="Known gap: PRAGMA foreign_keys is only set inside init_db().", strict=False)
def test_db_rejects_trip_for_nonexistent_journey(db_client):
    resp = db_client.post(
        "/api/trips", json={"user_id": 1, "journey_id": 9999, "duration": 1, "days": []}
    )
    assert resp.status_code >= 400


@pytest.mark.xfail(reason="Known gap: database service has no authentication of its own.", strict=False)
def test_db_service_refuses_unauthenticated_deletes(db_client):
    assert db_client.delete("/api/trips/1").status_code in (401, 403)


def test_fake_response_helper_sanity():
    assert FakeResponse(200, {"a": 1}).json() == {"a": 1}