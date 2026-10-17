"""Tests for the shared Multi-Agent Server. The LLM is mocked, so no Ollama is needed."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as server_app  # noqa: E402
import coordinator  # noqa: E402
import llm  # noqa: E402

EVIDENCE = [
    {"name": "Kyoto Zen Garden Inn", "city_area": "Kyoto", "facilities": ["wifi", "breakfast"],
     "avg_rating": 4.7, "min_price": 85.0},
    {"name": "Kyoto Riverside Ryokan", "city_area": "Kyoto", "facilities": ["wifi", "breakfast"],
     "avg_rating": 4.9, "min_price": 130.0},
]


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client():
    server_app.app.config["TESTING"] = True
    with server_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def fake_chat(system_prompt, user_prompt, model=None, timeout=None):
        calls.append(system_prompt.split(".")[0])
        return "fake model output"

    monkeypatch.setattr(llm, "chat", fake_chat)
    return calls


@pytest.fixture
def llm_down(monkeypatch):
    def broken_chat(*args, **kwargs):
        raise llm.LLMError("connection refused")

    monkeypatch.setattr(llm, "chat", broken_chat)


def _run(client, **overrides):
    body = {"user_request": "Which Kyoto stays include breakfast?", "feature": "accommodation",
            "evidence": EVIDENCE}
    body.update(overrides)
    return client.post("/workflow", json=body)


def _lines(path, name):
    return [json.loads(line) for line in (path / name).read_text(encoding="utf-8").splitlines()]


class TestWorkflow:
    def test_runs_planner_worker_reviewer_in_order(self, client, fake_llm):
        resp = _run(client)
        assert resp.status_code == 200
        record = resp.get_json()
        assert list(record["steps"]) == ["planner", "worker", "reviewer"]
        # fake_llm records the first sentence of each system prompt, in call order
        assert [s.split()[3] for s in fake_llm] == ["Planner", "Worker", "Reviewer"]
        assert record["status"] == "pending_human_review"
        assert record["human_decision"] == {"status": "pending"}
        assert record["degraded"] is False
        assert record["evidence_count"] == 2

    def test_history_and_audit_logs_are_written(self, client, fake_llm, isolated_data):
        workflow_id = _run(client).get_json()["workflow_id"]
        history = _lines(isolated_data, "workflow_history.jsonl")
        audit = _lines(isolated_data, "coordination_audit.jsonl")
        assert history[0]["workflow_id"] == workflow_id
        events = [a["event"] for a in audit if a["workflow_id"] == workflow_id]
        assert events == ["workflow_created", "agent_step_completed", "agent_step_completed",
                          "agent_step_completed", "awaiting_human_review"]

    def test_llm_failure_falls_back_and_still_reaches_human_review(self, client, llm_down):
        record = _run(client).get_json()
        assert record["degraded"] is True
        assert record["status"] == "pending_human_review"
        worker = record["steps"]["worker"]
        assert worker["status"] == "fallback"
        assert "Kyoto Zen Garden Inn" in worker["output"]
        assert "model was unavailable" in " ".join(record["steps"]["reviewer"]["checks"])

    def test_no_evidence_is_flagged_by_the_reviewer(self, client, llm_down):
        record = _run(client, evidence=None).get_json()
        assert record["evidence_count"] == 0
        assert "Insufficient evidence" in record["steps"]["worker"]["output"]
        assert any("No evidence" in c for c in record["steps"]["reviewer"]["checks"])

    def test_figures_not_in_evidence_are_flagged(self, client, monkeypatch):
        def invented(system_prompt, user_prompt, model=None, timeout=None):
            return "RESULT: Zen Garden Inn costs $999 per night.\nSOURCES: Kyoto Zen Garden Inn"

        monkeypatch.setattr(llm, "chat", invented)
        record = _run(client).get_json()
        assert any("999" in c for c in record["steps"]["reviewer"]["checks"])

    def test_mcp_tool_wrapper_and_error_dict_are_normalised(self, client, llm_down):
        wrapped = {"tool": "accommodations_by_city", "input": {"city_area": "Kyoto"}, "result": EVIDENCE}
        assert _run(client, evidence=wrapped).get_json()["evidence_count"] == 2
        assert _run(client, evidence={"error": "database unreachable"}).get_json()["evidence_count"] == 0

    def test_request_is_required(self, client):
        resp = client.post("/workflow", json={"feature": "accommodation"})
        assert resp.status_code == 400
        assert "user_request" in resp.get_json()["error"]

    def test_request_length_is_limited(self, client):
        resp = _run(client, user_request="x" * (coordinator.MAX_REQUEST_CHARS + 1))
        assert resp.status_code == 400


class TestHumanReview:
    def _create(self, client, fake_llm):
        return _run(client).get_json()["workflow_id"]

    @pytest.mark.parametrize("decision,status", [
        ("accept", "accepted"), ("partial", "partially_accepted"), ("reject", "rejected"),
    ])
    def test_decisions_update_the_status(self, client, fake_llm, decision, status):
        workflow_id = self._create(client, fake_llm)
        resp = client.post(f"/workflow/{workflow_id}/decision", json={"decision": decision, "note": "ok"})
        assert resp.status_code == 200
        record = resp.get_json()
        assert record["status"] == status
        assert record["human_decision"]["note"] == "ok"
        assert client.get(f"/workflow/{workflow_id}").get_json()["status"] == status

    def test_correct_requires_corrected_output(self, client, fake_llm):
        workflow_id = self._create(client, fake_llm)
        resp = client.post(f"/workflow/{workflow_id}/decision", json={"decision": "correct"})
        assert resp.status_code == 400
        resp = client.post(f"/workflow/{workflow_id}/decision",
                           json={"decision": "correct", "corrected_output": "Both inns include breakfast."})
        assert resp.status_code == 200
        assert resp.get_json()["human_decision"]["corrected_output"] == "Both inns include breakfast."

    def test_a_workflow_can_only_be_decided_once(self, client, fake_llm):
        workflow_id = self._create(client, fake_llm)
        client.post(f"/workflow/{workflow_id}/decision", json={"decision": "accept"})
        resp = client.post(f"/workflow/{workflow_id}/decision", json={"decision": "reject"})
        assert resp.status_code == 409

    def test_invalid_decision_and_unknown_id(self, client, fake_llm):
        workflow_id = self._create(client, fake_llm)
        assert client.post(f"/workflow/{workflow_id}/decision", json={"decision": "maybe"}).status_code == 400
        assert client.post("/workflow/doesnotexist/decision", json={"decision": "accept"}).status_code == 404
        assert client.get("/workflow/doesnotexist").status_code == 404

    def test_decision_is_audited(self, client, fake_llm, isolated_data):
        workflow_id = self._create(client, fake_llm)
        client.post(f"/workflow/{workflow_id}/decision", json={"decision": "accept"})
        audit = _lines(isolated_data, "coordination_audit.jsonl")
        assert audit[-1]["event"] == "human_decision"
        assert audit[-1]["status"] == "accepted"


class TestStatus:
    def test_health(self, client):
        body = client.get("/").get_json()
        assert body["service"] == "multi-agent-server"
        assert body["agents"] == ["planner", "worker", "reviewer"]

    def test_status_counts_latest_snapshot_per_workflow(self, client, fake_llm):
        first = _run(client).get_json()["workflow_id"]
        second = _run(client).get_json()["workflow_id"]
        client.post(f"/workflow/{first}/decision", json={"decision": "accept"})
        summary = client.get("/workflow/status").get_json()
        assert summary["total"] == 2
        assert summary["by_status"] == {"accepted": 1, "pending_human_review": 1}
        assert summary["latest"]["workflow_id"] == second

    def test_status_is_empty_before_any_workflow(self, client):
        assert client.get("/workflow/status").get_json() == {"total": 0, "by_status": {}, "latest": None}