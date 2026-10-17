"""Fixtures for the post_commit suite.

The backend's three outbound dependencies (shared-api sessions, the database
service, and Ollama) are replaced with in-process fakes, so these tests run
anywhere with only `pip install -r tests/requirements.txt`.
"""

import sqlite3

import pytest
from helpers import ROOT, FakeServices, issue_token, load_module


@pytest.fixture(scope="session")
def backend_module():
    return load_module("backend_app_under_test", ROOT / "backend" / "app.py")


@pytest.fixture
def services(backend_module, monkeypatch):
    fake = FakeServices()
    monkeypatch.setattr(backend_module.requests, "get", fake.get)
    monkeypatch.setattr(backend_module.requests, "post", fake.post)
    monkeypatch.setattr(backend_module.requests, "put", fake.put)
    monkeypatch.setattr(backend_module.requests, "delete", fake.delete)

    def no_llm(*_a, **_k):
        raise RuntimeError("LLM disabled in tests")

    # generate_ai_itinerary falls back to its random-choice path when the LLM fails.
    monkeypatch.setattr(backend_module.client.chat.completions, "create", no_llm)
    return fake


@pytest.fixture
def client(backend_module, services):
    backend_module.app.config["TESTING"] = True
    return backend_module.app.test_client()


@pytest.fixture
def auth():
    def _auth(user_id=1, **token_options):
        return {"Authorization": f"Bearer {issue_token(user_id, **token_options)}"}

    return _auth


@pytest.fixture
def db_client(tmp_path, monkeypatch):
    """The database service, pointed at a throwaway SQLite file instead of journeybuddy.db."""
    real_connect = sqlite3.connect
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(sqlite3, "connect", lambda *_a, **_k: real_connect(db_file))
    module = load_module("database_app_under_test", ROOT / "database" / "init_db.py")
    module.app.config["TESTING"] = True
    return module.app.test_client()