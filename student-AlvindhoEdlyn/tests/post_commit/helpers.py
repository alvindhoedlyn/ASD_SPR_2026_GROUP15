"""Shared test doubles for the post_commit suite (no network, no Docker, no LLM)."""

import importlib.util
import time
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parents[2]

# Throwaway key, only ever used to sign tokens inside these tests.
JWT_SECRET = "test-only-secret-key-with-enough-length-32b"  # pragma: allowlist secret


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("response has no JSON body")
        return self._payload


def issue_token(user_id, *, secret=JWT_SECRET, expires_in=3600, algorithm="HS256", **extra):
    now = int(time.time())
    claims = {"user_id": user_id, "iat": now, "exp": now + expires_in, **extra}
    return jwt.encode(claims, secret, algorithm=algorithm)


def verify_like_shared_api(token: str) -> FakeResponse:
    """Stands in for shared-api's /api/verify-session: strict HS256 + required claims."""
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "user_id"]},
        )
    except jwt.PyJWTError:
        return FakeResponse(401, {"error": "invalid or expired session"})
    return FakeResponse(200, {"user_id": claims["user_id"]})


class FakeServices:
    """In-memory replacement for shared-api + the database service."""

    def __init__(self):
        self.trips = [
            {"trip_ID": 1, "user_ID": 1, "journey_ID": 1, "duration": 2, "preferences": None},
            {"trip_ID": 2, "user_ID": 2, "journey_ID": 1, "duration": 1, "preferences": None},
        ]
        self.locations = ["Bondi Beach", "Opera House"]
        self.calls = []
        self.created_payload = None

    # ---- GET ----
    def get(self, url, params=None, timeout=None, **_):
        self.calls.append(("GET", url))
        if url.endswith("/api/verify-session"):
            return verify_like_shared_api((params or {}).get("token", ""))
        if url.endswith("/api/trips"):
            return FakeResponse(200, self.trips)
        if url.endswith("/details"):
            return FakeResponse(200, {"locations": self.locations})
        if url.endswith("/days"):
            return FakeResponse(
                200, [{"itinerary": "City tour", "weather": "Sunny", "activity": "City tour"}]
            )
        if "/api/journeys/" in url:
            if int(url.rsplit("/", 1)[1]) != 1:
                return FakeResponse(404, {"error": "Journey not found"})
            return FakeResponse(
                200, {"journey_id": 1, "label": "Sydney Weekend", "locations": self.locations}
            )
        if url.endswith("/api/journeys"):
            return FakeResponse(200, [{"journey_id": 1, "label": "Sydney Weekend"}])
        return FakeResponse(404, {"error": f"unrouted {url}"})

    # ---- POST / PUT / DELETE ----
    def post(self, url, json=None, timeout=None, **_):
        self.calls.append(("POST", url))
        if url.endswith("/api/trips"):
            self.created_payload = json
            days = [
                {"day_id": i, **{k: d[k] for k in ("day_number", "location", "weather", "itinerary", "activity")}}
                for i, d in enumerate(json["days"], start=1)
            ]
            return FakeResponse(201, {"trip_id": 99, "days": days})
        return FakeResponse(200, {"status": "ok"})

    def put(self, url, json=None, timeout=None, **_):
        self.calls.append(("PUT", url))
        return FakeResponse(200, {"message": "ok"})

    def delete(self, url, timeout=None, **_):
        self.calls.append(("DELETE", url))
        return FakeResponse(200, {"message": "ok"})

    def writes(self):
        return [c for c in self.calls if c[0] in ("PUT", "DELETE") or (c[0] == "POST" and "/api/trips" in c[1])]