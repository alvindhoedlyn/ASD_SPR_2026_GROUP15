"""Tests for the attraction feature's Release 1 validation modes."""

import importlib.util
from pathlib import Path
from unittest.mock import patch


STUDENT_DIR = Path(__file__).resolve().parents[1]
AGENTIC_LOOP_DIR = STUDENT_DIR / "agentic_loop"


def load_module(module_name, relative_path):
    module_path = AGENTIC_LOOP_DIR / relative_path
    module_spec = importlib.util.spec_from_file_location(
        module_name,
        module_path
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


mcp_collector = load_module(
    "test_trongdao_mcp_collector",
    "collectors/mcp_collector.py"
)
rag_collector = load_module(
    "test_trongdao_rag_collector",
    "collectors/rag_collector.py"
)
devops_collector = load_module(
    "test_trongdao_devops_collector",
    "collectors/devops_collector.py"
)
review_config = load_module(
    "test_trongdao_review_config",
    "config/review_config.py"
)
agentic_main = load_module(
    "test_trongdao_agentic_main",
    "main.py"
)


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
        self.text = str(data)

    def json(self):
        return self.data


def test_release_one_validation_modes_are_configured():
    mode_config = review_config.build_mode_config()

    assert set(mode_config) == {
        "db",
        "endpoints",
        "devops",
        "mcp",
        "rag"
    }
    assert mode_config["mcp"].two_stage is True
    assert mode_config["rag"].two_stage is True

    for prompt_family in ("mcp", "rag"):
        prompt_root = STUDENT_DIR / "prompts" / prompt_family

        assert (
            prompt_root / "implementation/system_prompt.txt"
        ).is_file()
        assert (
            prompt_root / "implementation/task_prompt.txt"
        ).is_file()
        assert (
            prompt_root / "review/review_prompt.txt"
        ).is_file()

    assert set(agentic_main.COLLECTORS) == set(mode_config)
    assert set(agentic_main.PIPELINES) == set(mode_config)
    assert agentic_main.COLLECTORS["mcp"] is (
        agentic_main.mcp_collector.collect
    )
    assert agentic_main.COLLECTORS["rag"] is (
        agentic_main.rag_collector.collect
    )


def test_devops_collector_enforces_local_release_one_services():
    ok, evidence = devops_collector.collect(
        STUDENT_DIR,
        STUDENT_DIR.parent
    )

    assert ok is True
    assert "local/non-containerised" in evidence
    assert "MCP disabled in CI: True" in evidence
    assert "RAG disabled in CI: True" in evidence
    assert "Backend uses local MCP address: True" in evidence
    assert "Backend uses local RAG address: True" in evidence


def test_mcp_collector_validates_both_attraction_tools():
    city_result = {
        "result": {
            "structuredContent": {
                "city": "Sydney",
                "category": "nature",
                "count": 1,
                "attractions": [
                    {
                        "attraction_id": 2,
                        "attraction_name": "Royal Botanic Garden",
                        "category": "nature"
                    }
                ]
            }
        }
    }
    details_result = {
        "result": {
            "structuredContent": {
                "attraction_id": 2,
                "attraction_name": "Royal Botanic Garden",
                "category": "nature"
            }
        }
    }

    with patch.object(
        mcp_collector.requests,
        "post",
        side_effect=[
            FakeResponse(city_result),
            FakeResponse(details_result)
        ]
    ) as mock_post:
        ok, evidence = mcp_collector.collect(
            STUDENT_DIR,
            STUDENT_DIR.parent
        )

    assert ok is True
    assert "attractions_by_city" in evidence
    assert "attraction_details" in evidence
    assert mock_post.call_count == 2

    first_request = mock_post.call_args_list[0]
    assert first_request.args[0].endswith("/api/mcp/call")
    assert first_request.kwargs["headers"] == {
        "X-MCP-Mode": "on"
    }
    assert first_request.kwargs["json"] == {
        "tool": "attractions_by_city",
        "arguments": {
            "city": "Sydney",
            "category": "nature"
        }
    }


def test_mcp_collector_rejects_unstructured_output():
    with patch.object(
        mcp_collector.requests,
        "post",
        return_value=FakeResponse({"result": {}})
    ):
        ok, evidence = mcp_collector.collect(
            STUDENT_DIR,
            STUDENT_DIR.parent
        )

    assert ok is False
    assert "no structured MCP content" in evidence


def test_rag_collector_validates_grounding_and_refusal():
    grounded_result = {
        "status": "success",
        "answer": (
            "The Sydney Opera House has wheelchair-accessible "
            "entrances and guided tours."
        ),
        "citations": [
            {
                "chunk_id": "location_1",
                "source_id": "student-TrongDao-database:/places/1",
                "authority_tier": "tier_1"
            }
        ],
        "confidence_category": "High"
    }
    insufficient_result = {
        "status": "insufficient_context",
        "answer": (
            "Insufficient context available to answer this question."
        ),
        "citations": [],
        "confidence_category": "Insufficient"
    }

    with patch.object(
        rag_collector.requests,
        "post",
        side_effect=[
            FakeResponse(grounded_result),
            FakeResponse(insufficient_result)
        ]
    ) as mock_post:
        ok, evidence = rag_collector.collect(
            STUDENT_DIR,
            STUDENT_DIR.parent
        )

    assert ok is True
    assert "confidence High" in evidence
    assert "1 citation(s)" in evidence
    assert "insufficient_context" in evidence
    assert mock_post.call_count == 2

    first_request = mock_post.call_args_list[0]
    assert first_request.args[0].endswith("/api/rag/answer")
    assert first_request.kwargs["headers"] == {
        "X-RAG-Mode": "on"
    }
    assert first_request.kwargs["json"] == {
        "query": (
            "What accessibility information does the "
            "Sydney Opera House have?"
        ),
        "k": 5
    }


def test_rag_collector_rejects_unsupported_answer():
    grounded_result = {
        "status": "success",
        "answer": "Grounded attraction answer.",
        "citations": [
            {
                "chunk_id": "location_1",
                "source_id": "student-TrongDao-database:/places/1",
                "authority_tier": "tier_1"
            }
        ],
        "confidence_category": "High"
    }
    hallucinated_result = {
        "status": "success",
        "answer": "A Sydney attraction offers Mars tours.",
        "citations": [],
        "confidence_category": "High"
    }

    with patch.object(
        rag_collector.requests,
        "post",
        side_effect=[
            FakeResponse(grounded_result),
            FakeResponse(hallucinated_result)
        ]
    ):
        ok, evidence = rag_collector.collect(
            STUDENT_DIR,
            STUDENT_DIR.parent
        )

    assert ok is False
    assert "was not rejected" in evidence
