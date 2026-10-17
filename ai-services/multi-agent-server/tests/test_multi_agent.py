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
        role = system_prompt.split()[3]
        if role == "Worker":
            return "RESULT: fake model output\nSOURCES: none"
        if role == "Reviewer":
            return "VERDICT: PASS\nRISKS: none\nRECOMMENDATION: none"
        return "GOAL: fake plan"

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


BREAKFAST_EVIDENCE = [
    {"name": "Kyoto Riverside Ryokan", "facilities": ["wifi", "breakfast"]},
    {"name": "Kyoto Zen Garden Inn", "facilities": ["wifi", "breakfast"]},
    {"name": "Kyoto Budget Hostel", "facilities": ["wifi"]},
]


def _llm_returning(monkeypatch, worker_text, reviewer_text="VERDICT: PASS\nRISKS: none"):
    """Planner/Worker/Reviewer get different canned answers (told apart by system prompt)."""
    def chat(system_prompt, user_prompt, model=None, timeout=None):
        role = system_prompt.split()[3]
        if role == "Worker":
            return worker_text
        if role == "Reviewer":
            return reviewer_text
        return "GOAL: x"

    monkeypatch.setattr(llm, "chat", chat)


class TestReviewerChecks:
    def test_incomplete_answer_is_flagged_and_pass_is_overridden(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Riverside Ryokan includes breakfast.")
        record = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()
        reviewer = record["steps"]["reviewer"]
        assert any("Kyoto Zen Garden Inn" in c and "'breakfast'" in c for c in reviewer["checks"])
        assert "VERDICT: REVISE" in reviewer["output"]
        assert "VERDICT: PASS" not in reviewer["output"]
        assert reviewer["verified"] == []

    def test_stay_without_the_facility_is_flagged(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Riverside Ryokan, Kyoto Zen Garden Inn and Kyoto Budget Hostel.")
        record = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()
        checks = record["steps"]["reviewer"]["checks"]
        assert any("Kyoto Budget Hostel" in c and "does not list 'breakfast'" in c for c in checks)

    def test_complete_answer_passes_with_no_checks(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Riverside Ryokan and Kyoto Zen Garden Inn include breakfast.")
        reviewer = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["reviewer"]
        assert reviewer["checks"] == []
        assert "VERDICT: PASS" in reviewer["output"]
        assert any("All 2 item(s) listing 'breakfast' were named" in v for v in reviewer["verified"])

    def test_stays_cited_only_in_the_sources_line_are_not_counted_as_named(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Riverside Ryokan and Kyoto Zen Garden Inn include breakfast.\n"
                                    "SOURCES: Evidence: Kyoto Riverside Ryokan, Kyoto Zen Garden Inn, Kyoto Budget Hostel")
        reviewer = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["reviewer"]
        assert reviewer["checks"] == []

    def test_missing_verdict_line_is_added(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Riverside Ryokan includes breakfast.",
                       reviewer_text="RISKS: none identified.")
        reviewer = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["reviewer"]
        assert reviewer["output"].startswith("VERDICT: REVISE (set by automated checks)")

    def test_negated_requests_skip_the_coverage_check(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Budget Hostel.")
        record = _run(client, user_request="Which stays do not include breakfast?",
                      evidence=BREAKFAST_EVIDENCE).get_json()
        assert record["steps"]["reviewer"]["checks"] == []


class TestEvidenceBrief:
    def test_brief_drops_noise_and_keeps_facilities(self):
        import evidence

        text = evidence.brief([{"name": "Inn", "created_at": "2026-10-01", "images": [],
                                "facilities": ["wifi", "breakfast"], "avg_rating": 4.7}])
        assert text == "- Inn | facilities: wifi, breakfast; avg_rating: 4.7"

    def test_agent_prompts_use_the_brief_form(self, client, monkeypatch):
        seen = []

        def chat(system_prompt, user_prompt, model=None, timeout=None):
            seen.append(user_prompt)
            return "ok"

        monkeypatch.setattr(llm, "chat", chat)
        _run(client, evidence=BREAKFAST_EVIDENCE)
        assert any("- Kyoto Riverside Ryokan | facilities: wifi, breakfast" in p for p in seen)
        assert not any('"facilities":' in p for p in seen)


class TestSmallModelFailures:
    def test_prompt_echo_is_treated_as_a_failed_step(self, client, monkeypatch):
        monkeypatch.setattr(llm, "chat", lambda *a, **k: "Request: Which stays include breakfast\nEvidence (3 item(s)):")
        record = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()
        assert record["degraded"] is True
        worker = record["steps"]["worker"]
        assert worker["status"] == "fallback"
        assert "repeated the prompt" in worker["error"]

    def test_worker_fallback_only_lists_stays_with_the_requested_facility(self, client, llm_down):
        worker = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["worker"]
        assert "2 of 3 item(s) list 'breakfast'" in worker["output"]
        assert "Kyoto Riverside Ryokan" in worker["output"]
        assert "Kyoto Budget Hostel" not in worker["output"]

    def test_fallback_answer_passes_the_reviewer_coverage_check(self, client, llm_down):
        reviewer = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["reviewer"]
        assert not any("does not list" in c or "not mentioned" in c for c in reviewer["checks"])

    def test_fallback_counts_are_not_reported_as_invented_figures(self, client, llm_down):
        record = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()
        assert not any("figures not found" in c for c in record["steps"]["reviewer"]["checks"])

    def test_worker_fallback_says_so_when_no_stay_has_every_requested_facility(self, client, llm_down):
        evidence = [{"name": "Wifi Inn", "facilities": ["wifi"]}, {"name": "Morning Inn", "facilities": ["breakfast"]}]
        worker = _run(client, user_request="Which stays have wifi and breakfast?", evidence=evidence).get_json()["steps"]["worker"]
        assert "No evidence item lists 'breakfast' and 'wifi'" in worker["output"]


class TestFormatEnforcement:
    def test_reviewer_that_rewrites_the_worker_answer_is_replaced_by_the_fallback(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Riverside Ryokan and Kyoto Zen Garden Inn include breakfast.",
                       reviewer_text="RESULT: Kyoto Riverside Ryokan (facilities: wifi)\nSOURCES: Kyoto Riverside Ryokan")
        reviewer = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["reviewer"]
        assert reviewer["status"] == "fallback"
        assert "required format" in reviewer["error"]
        assert "facilities: wifi" not in reviewer["output"]
        assert reviewer["output"].startswith("VERDICT: PASS")

    def test_worker_reply_without_a_result_label_uses_the_fallback(self, client, monkeypatch):
        _llm_returning(monkeypatch, "Sure! Kyoto Riverside Ryokan is a nice place.")
        worker = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["worker"]
        assert worker["status"] == "fallback"
        assert "2 of 3 item(s) list 'breakfast'" in worker["output"]


class _FakeReply:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class TestModelsPerRole:
    def test_each_role_has_its_own_default_model_and_env_overrides_it(self, monkeypatch):
        from agents import base

        for role in ("PLANNER", "WORKER", "REVIEWER"):
            monkeypatch.delenv(f"{role}_MODEL", raising=False)
        assert base.model_for("planner") == "qwen2.5:0.5b"
        assert base.model_for("worker") == "qwen2.5:0.5b"
        assert base.model_for("reviewer") == "llama3.1:8b"
        monkeypatch.setenv("REVIEWER_MODEL", "qwen2.5:0.5b")
        assert base.model_for("reviewer") == "qwen2.5:0.5b"

    def test_the_step_records_which_model_ran(self, client, fake_llm, monkeypatch):
        for role in ("PLANNER", "WORKER", "REVIEWER"):
            monkeypatch.delenv(f"{role}_MODEL", raising=False)
        steps = _run(client).get_json()["steps"]
        assert [steps[a]["model"] for a in ("planner", "worker", "reviewer")] == [
            "qwen2.5:0.5b", "qwen2.5:0.5b", "llama3.1:8b"]


class TestReasoningModels:
    def test_think_block_is_removed_and_reasoning_gets_a_bigger_budget(self, monkeypatch):
        sent = {}

        def post(url, json=None, timeout=None):
            sent["payload"], sent["timeout"] = json, timeout
            return _FakeReply("<think>VERDICT: PASS is not my answer yet...</think>\nVERDICT: REVISE\nRISKS: none")

        monkeypatch.setattr(llm.requests, "post", post)
        reply = llm.chat("system", "user", model="deepseek-r1:8b")
        assert reply == "VERDICT: REVISE\nRISKS: none"
        assert sent["payload"]["max_tokens"] == llm.REASONING_MAX_TOKENS
        assert sent["timeout"] == llm.REASONING_TIMEOUT_SECONDS

    def test_normal_models_keep_the_small_budget(self, monkeypatch):
        sent = {}

        def post(url, json=None, timeout=None):
            sent["payload"], sent["timeout"] = json, timeout
            return _FakeReply("RESULT: ok")

        monkeypatch.setattr(llm.requests, "post", post)
        assert llm.chat("system", "user", model="qwen2.5:0.5b") == "RESULT: ok"
        assert sent["payload"]["max_tokens"] == llm.MAX_TOKENS
        assert sent["timeout"] == llm.STEP_TIMEOUT_SECONDS

    def test_unfinished_thinking_is_an_error_so_the_agent_falls_back(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeReply("<think>still thinking about"))
        with pytest.raises(llm.LLMError, match="ran out of tokens"):
            llm.chat("system", "user", model="deepseek-r1:8b")


class TestVerifiedByRules:
    def test_rule_results_are_shown_even_when_the_model_review_contradicts_them(self, client, monkeypatch):
        _llm_returning(monkeypatch, "RESULT: Kyoto Riverside Ryokan and Kyoto Zen Garden Inn include breakfast.",
                       reviewer_text="VERDICT: FAIL\nRISKS: Kyoto Zen Garden Inn has no breakfast.\nRECOMMENDATION: reject")
        reviewer = _run(client, evidence=BREAKFAST_EVIDENCE).get_json()["steps"]["reviewer"]
        assert "no breakfast" in reviewer["output"]          # the model's (wrong) opinion is kept as written
        assert reviewer["checks"] == []                      # but the rules found no problem
        assert reviewer["verified"]                          # and say what they confirmed


class TestReviewerPromptAndTimeout:
    def test_reviewer_gets_a_longer_timeout_and_a_small_prompt(self, client, monkeypatch):
        seen = {}

        def chat(system_prompt, user_prompt, model=None, timeout=None):
            seen[system_prompt.split()[3]] = (user_prompt, timeout)
            return "RESULT: x\nVERDICT: PASS\nRISKS: none"

        monkeypatch.setattr(llm, "chat", chat)
        for name in ("PLANNER", "WORKER", "REVIEWER"):
            monkeypatch.delenv(f"{name}_TIMEOUT_SECONDS", raising=False)
        evidence = [{"name": "Inn", "avg_rating": 4.7, "description": "A long description " * 20,
                     "facilities": ["wifi", "breakfast"]}]
        _run(client, evidence=evidence)
        prompt, timeout = seen["Reviewer"]
        assert timeout == 300.0
        assert seen["Worker"][1] is None
        assert "- Inn | facilities: wifi, breakfast" in prompt
        assert "avg_rating" not in prompt and "long description" not in prompt

    def test_timeout_can_be_set_per_role(self, monkeypatch):
        from agents import base

        monkeypatch.setenv("REVIEWER_TIMEOUT_SECONDS", "45")
        assert base.timeout_for("reviewer") == 45.0
        assert base.timeout_for("planner") is None


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
        saved = client.get(f"/workflow/{workflow_id}").get_json()
        assert saved["status"] == status

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
        bad = client.post(f"/workflow/{workflow_id}/decision", json={"decision": "maybe"})
        assert bad.status_code == 400
        missing = client.post("/workflow/doesnotexist/decision", json={"decision": "accept"})
        assert missing.status_code == 404
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