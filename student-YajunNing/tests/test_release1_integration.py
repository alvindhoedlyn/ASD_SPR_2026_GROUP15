import os
import sys
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
REPOSITORY_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

from app import app
from rag_client import ask_rag


class Release1IntegrationApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.search = {
            "origin": "Sydney",
            "destination": "Tokyo",
            "departure_date": "2026-10-10",
            "return_date": "2026-10-17",
            "max_budget": 1000,
            "preference": "best_overall",
        }

    @patch.dict(os.environ, {"MCP_ENABLED": "true"})
    @patch("app.call_mcp_tool")
    def test_frontend_backend_mcp_endpoint_returns_structured_tool_result(self, tool_mock):
        tool_mock.return_value = {
            "status": "success",
            "tool": "recommend_flights",
            "result": {
                "recommendations": [{"flight_number": "QF25", "price_aud": 890}],
            },
        }
        response = self.client.post("/api/mcp/recommend-flights", json=self.search)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tool"], "recommend_flights")
        tool_mock.assert_called_once()

    @patch.dict(os.environ, {"RAG_ENABLED": "true"})
    @patch("app.ask_rag")
    def test_rag_endpoint_preserves_citations_and_confidence(self, rag_mock):
        rag_mock.return_value = {
            "status": "success",
            "answer": "QF25 is a direct catalogue flight costing AUD $890.",
            "citations": [{"source_id": "student-YajunNing-database:/flights/4"}],
            "confidence_category": "High",
        }
        response = self.client.post("/api/rag/answer", json={"query": "What does QF25 cost?"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["confidence_category"], "High")
        self.assertEqual(len(data["citations"]), 1)

    @patch.dict(os.environ, {"RAG_ENABLED": "true"})
    @patch("app.ask_rag")
    def test_rag_endpoint_returns_safe_insufficient_context(self, rag_mock):
        rag_mock.return_value = {
            "status": "insufficient_context",
            "answer": "Insufficient context available to answer this question.",
            "citations": [],
            "confidence_category": "Insufficient",
        }
        response = self.client.post("/api/rag/answer", json={"query": "Which flight serves Mars?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "insufficient_context")

    @patch.dict(os.environ, {"MCP_ENABLED": "false", "RAG_ENABLED": "false"})
    def test_ci_can_disable_local_mcp_and_rag(self):
        mcp_response = self.client.post("/api/mcp/recommend-flights", json=self.search)
        rag_response = self.client.post("/api/rag/answer", json={"query": "QF25"})
        self.assertEqual(mcp_response.status_code, 503)
        self.assertEqual(rag_response.status_code, 503)
        self.assertEqual(mcp_response.get_json()["status"], "disabled")
        self.assertEqual(rag_response.get_json()["status"], "disabled")


class SharedRagClientTests(unittest.TestCase):
    @patch.dict(os.environ, {"RAG_ENABLED": "true", "RAG_SERVICE_URL": "http://localhost:8100"})
    @patch("rag_client.requests.post")
    def test_shared_rag_response_is_normalised_for_flight_frontend(self, post_mock):
        post_mock.return_value.raise_for_status.return_value = None
        post_mock.return_value.json.return_value = {
            "question": "What does JQ11 cost?",
            "answer": "Jetstar JQ11 costs AUD 620.",
            "sources": [{"document": "flights.md", "section": "Jetstar JQ11"}],
            "confidence": "high",
            "retrieved_context": [{"source": "flights.md"}],
            "model": "qwen2.5:0.5b",
            "generation_mode": "validated_fallback",
            "service": "journeybuddy-shared-rag",
        }

        result = ask_rag("What does JQ11 cost?")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["confidence_category"], "High")
        self.assertEqual(result["generation_mode"], "validated_fallback")
        self.assertEqual(result["citations"][0]["source_id"], "flights.md#Jetstar JQ11")
        post_mock.assert_called_once_with(
            "http://localhost:8100/query",
            json={"question": "What does JQ11 cost?"},
            timeout=120,
        )


class SharedRagGroundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server_path = REPOSITORY_DIR / "ai-services" / "rag-server" / "server.py"
        spec = importlib.util.spec_from_file_location("journeybuddy_rag_server", server_path)
        cls.rag_server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rag_server)

    def test_flight_constraints_reject_an_ungrounded_model_answer(self):
        retrieved_chunks = [
            {
                "source": "flights.md",
                "heading": "Direct Sydney to Tokyo flights below AUD 700",
                "text": (
                    "Jetstar flight JQ11 travels from Sydney (SYD) to Tokyo (NRT). "
                    "It departs at 11:10, arrives at 19:20, costs AUD 620, takes "
                    "610 minutes, and has zero stops."
                ),
                "score": 1.0,
            }
        ]

        with patch.object(
            self.rag_server,
            "generate_grounded_answer",
            return_value="Qantas QF25 is below AUD 700 and costs AUD 890.",
        ):
            result = self.rag_server.build_answer(
                "Which direct Sydney to Tokyo flight costs less than AUD 700?",
                retrieved_chunks,
            )

        self.assertEqual(result["generation_mode"], "validated_fallback")
        self.assertIn("Jetstar JQ11", result["answer"])
        self.assertIn("AUD 620", result["answer"])
        self.assertNotIn("QF25", result["answer"])
        self.assertEqual(
            result["sources"],
            [{
                "document": "flights.md",
                "section": "Direct Sydney to Tokyo flights below AUD 700",
            }],
        )


if __name__ == "__main__":
    unittest.main()
