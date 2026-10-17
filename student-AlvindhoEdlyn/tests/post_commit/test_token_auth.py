"""Post-commit: PyJWT-based checks on how the backend handles session tokens.

The backend never decodes tokens itself; it forwards them to shared-api's
/api/verify-session. These tests plug a strict PyJWT verifier in as that
service and confirm the backend (a) fails closed on every bad token and
(b) takes the user's identity from the verified token, never from the client.
"""

import base64
import json
import time

import jwt
import pytest
from helpers import JWT_SECRET, FakeResponse, issue_token

pytestmark = pytest.mark.post_commit


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def b64url(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_valid_token_is_accepted(client):
    assert client.get("/api/trips", headers=bearer(issue_token(1))).status_code == 200


def test_expired_token_is_rejected(client):
    token = issue_token(1, expires_in=-60)
    assert client.get("/api/trips", headers=bearer(token)).status_code == 401


def test_token_signed_with_the_wrong_key_is_rejected(client):
    token = issue_token(1, secret="attacker-controlled-key-0123456789abcdef")
    assert client.get("/api/trips", headers=bearer(token)).status_code == 401


def test_alg_none_token_is_rejected(client):
    claims = {"user_id": 1, "exp": int(time.time()) + 3600}
    token = jwt.encode(claims, None, algorithm="none")
    assert client.get("/api/trips", headers=bearer(token)).status_code == 401


def test_token_without_expiry_is_rejected(client):
    token = jwt.encode({"user_id": 1}, JWT_SECRET, algorithm="HS256")
    assert client.get("/api/trips", headers=bearer(token)).status_code == 401


def test_token_without_user_claim_is_rejected(client):
    claims = {"exp": int(time.time()) + 3600}
    token = jwt.encode(claims, JWT_SECRET, algorithm="HS256")
    assert client.get("/api/trips", headers=bearer(token)).status_code == 401


def test_tampered_payload_with_original_signature_is_rejected(client):
    header, _payload, signature = issue_token(1).split(".")
    forged_claims = {"user_id": 2, "exp": int(time.time()) + 3600}
    forged = f"{header}.{b64url(forged_claims)}.{signature}"
    assert client.get("/api/trips", headers=bearer(forged)).status_code == 401


def test_garbage_token_is_rejected(client):
    assert client.get("/api/trips", headers=bearer("not.a.jwt")).status_code == 401


@pytest.mark.parametrize("header", ["", "Bearer", "Bearer ", "Basic abc123", "bearer lowercase", "Token abc"])
def test_malformed_authorization_header_is_rejected(client, header):
    assert client.get("/api/trips", headers={"Authorization": header}).status_code == 401


def test_each_token_only_sees_its_own_user(client):
    for user_id, trip_id in ((1, 1), (2, 2)):
        resp = client.get("/api/trips", headers=bearer(issue_token(user_id)))
        assert [t["trip_id"] for t in resp.get_json()] == [trip_id]


def test_authorization_header_wins_over_query_token(client):
    resp = client.get("/api/trips?token=garbage", headers=bearer(issue_token(1)))
    assert resp.status_code == 200


def test_query_param_token_still_works_as_documented_fallback(client):
    assert client.get(f"/api/trips?token={issue_token(1)}").status_code == 200


def test_rejection_does_not_echo_the_token(client):
    token = issue_token(1, expires_in=-60)
    body = client.get("/api/trips", headers=bearer(token)).get_data(as_text=True)
    assert token not in body


def test_auth_service_outage_fails_closed(client, backend_module, monkeypatch):
    def down(*_a, **_k):
        raise backend_module.requests.exceptions.ConnectionError("shared-api down")

    monkeypatch.setattr(backend_module.requests, "get", down)
    resp = client.get("/api/trips", headers=bearer(issue_token(1)))
    assert resp.status_code == 502


def test_malformed_auth_service_reply_fails_closed(client, backend_module, monkeypatch):
    monkeypatch.setattr(
        backend_module.requests, "get", lambda *_a, **_k: FakeResponse(200, {"unexpected": True})
    )
    assert client.get("/api/trips", headers=bearer(issue_token(1))).status_code == 502