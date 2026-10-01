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
    @patch.dict(os.environ, {"RAG_ENABLED": "true", "RAG_SERVICE_URL": "http://localhost:5100"})
    @patch("rag_client.requests.post")
    def test_shared_rag_response_is_normalised_for_flight_frontend(self, post_mock):
        post_mock.return_value.raise_for_status.return_value = None
        post_mock.return_value.json.return_value = {
            "status": "success",
            "query": "What does JQ11 cost?",
            "answer": "Jetstar JQ11 costs AUD 620.",
            "citations": [{"source_id": "flights.md#Jetstar JQ11"}],
            "confidence_category": "High",
            "generation_mode": "validated_fallback",
            "service": "journeybuddy-shared-rag",
        }

        result = ask_rag("What does JQ11 cost?")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["confidence_category"], "High")
        self.assertEqual(result["generation_mode"], "validated_fallback")
        self.assertEqual(result["citations"][0]["source_id"], "flights.md#Jetstar JQ11")
        post_mock.assert_called_once_with(
            "http://localhost:5100/answer",
            json={"query": "What does JQ11 cost?", "k": 5, "caller": "flight-recommender"},
            timeout=120,
        )


class SharedRagGroundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rag_dir = REPOSITORY_DIR / "ai-services" / "rag-server"
        sys.path.insert(0, str(rag_dir))
        pipeline_path = rag_dir / "rag_pipeline.py"
        spec = importlib.util.spec_from_file_location(
            "journeybuddy_shared_rag_pipeline", pipeline_path
        )
        cls.rag_pipeline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rag_pipeline)

    def test_shared_pipeline_accepts_grounded_flight_alias_match(self):
        retrieved = {
            "status": "success",
            "results": [
                {
                    "chunk_id": "flight_2",
                    "source_id": "student-YajunNing-database:/flights/2",
                    "authority_tier": "tier_1",
                    "source_type": "flight_database",
                    "text": (
                        "Flight: Jetstar JQ11. Route: SYD to NRT. "
                        "Departure time: 11:10. Arrival time: 19:20. "
                        "Price: AUD $620.0. Duration: 610 minutes. "
                        "Stops: 0; this flight is direct with no stops."
                    ),
                    "keyword_overlap": 3,
                    "query_coverage": 0.333,
                }
            ],
        }

        with patch.object(
            self.rag_pipeline, "retrieve_context", return_value=retrieved
        ), patch.object(
            self.rag_pipeline,
            "generate_grounded_answer",
            return_value="Qantas QF25 costs AUD 890.",
        ):
            result = self.rag_pipeline.answer_question(
                "Which direct Sydney to Tokyo flight costs less than AUD 700?"
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["confidence_category"], "High")
        self.assertEqual(result["generation_mode"], "validated_fallback")
        self.assertIn("Jetstar JQ11", result["answer"])
        self.assertIn("AUD $620", result["answer"])
        self.assertEqual(
            result["citations"][0]["source_id"],
            "student-YajunNing-database:/flights/2",
        )


if __name__ == "__main__":
    unittest.main()
