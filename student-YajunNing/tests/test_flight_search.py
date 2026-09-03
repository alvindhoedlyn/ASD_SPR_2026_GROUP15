import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import app
from llm_client import validate_grounded_explanation


TEST_FLIGHTS = [
    {"id": 1, "airline": "Scoot", "flight_number": "TR3", "origin": "SYD", "destination": "NRT", "departure_time": "13:35", "arrival_time": "08:00", "price_aud": 510, "duration_minutes": 865, "stops": 1},
    {"id": 2, "airline": "AirAsia X", "flight_number": "D7218", "origin": "SYD", "destination": "NRT", "departure_time": "10:45", "arrival_time": "08:25", "price_aud": 540, "duration_minutes": 880, "stops": 1},
    {"id": 3, "airline": "Philippine Airlines", "flight_number": "PR212", "origin": "SYD", "destination": "NRT", "departure_time": "11:30", "arrival_time": "08:10", "price_aud": 580, "duration_minutes": 920, "stops": 1},
    {"id": 4, "airline": "Qantas", "flight_number": "QF25", "origin": "SYD", "destination": "HND", "departure_time": "20:50", "arrival_time": "05:25", "price_aud": 890, "duration_minutes": 575, "stops": 0},
]


class FlightSearchApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.database_patcher = patch(
            "agentic_loop.get_available_flights",
            side_effect=lambda max_budget=None: TEST_FLIGHTS if max_budget is None else [
                flight for flight in TEST_FLIGHTS if flight["price_aud"] <= max_budget
            ],
        )
        self.database_patcher.start()
        self.addCleanup(self.database_patcher.stop)
        self.valid_search = {
            "origin": "Sydney",
            "destination": "Tokyo",
            "departure_date": "2026-09-10",
            "return_date": "2026-09-17",
            "max_budget": 1000,
            "preference": "cheapest",
        }

    def test_cheapest_results_are_sorted_by_price(self):
        response = self.client.post("/api/flight-searches", json=self.valid_search)
        self.assertEqual(response.status_code, 200)
        results = response.get_json()["recommendations"]
        self.assertEqual(len(results), 3)
        self.assertEqual([item["price_aud"] for item in results], [510, 540, 580])

    def test_budget_is_applied(self):
        payload = {**self.valid_search, "max_budget": 550}
        response = self.client.post("/api/flight-searches", json=payload)
        results = response.get_json()["recommendations"]
        self.assertTrue(all(item["price_aud"] <= 550 for item in results))

    def test_return_date_cannot_be_before_departure(self):
        payload = {**self.valid_search, "return_date": "2026-09-01"}
        response = self.client.post("/api/flight-searches", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("return_date", response.get_json()["error"])

    def test_unsupported_route_returns_empty_results(self):
        payload = {**self.valid_search, "origin": "Melbourne"}
        response = self.client.post("/api/flight-searches", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["recommendations"], [])

    def test_response_contains_four_stage_agentic_trace(self):
        response = self.client.post("/api/flight-searches", json=self.valid_search)
        trace = response.get_json()["agentic_loop"]["trace"]
        self.assertEqual(
            [step["stage"] for step in trace],
            ["Plan", "Act", "Observe", "Adapt"],
        )

    def test_agent_adapts_with_nearest_real_option_when_budget_is_too_low(self):
        payload = {**self.valid_search, "max_budget": 400}
        response = self.client.post("/api/flight-searches", json=payload)
        data = response.get_json()
        self.assertTrue(data["agentic_loop"]["adapted"])
        self.assertEqual(data["recommendations"][0]["flight_number"], "TR3")
        self.assertIn("AUD $110 more", data["message"])

    @patch("app.generate_ai_explanation", return_value="TR3 is the cheapest supplied option.")
    def test_ai_mode_returns_grounded_explanation(self, explanation_mock):
        payload = {**self.valid_search, "ai_mode": True}
        response = self.client.post("/api/flight-searches", json=payload)
        ai_result = response.get_json()["ai"]
        self.assertEqual(ai_result["status"], "ready")
        self.assertEqual(ai_result["explanation"], "TR3 is the cheapest supplied option.")
        explanation_mock.assert_called_once()

    @patch("app.generate_ai_explanation", side_effect=ValueError("ungrounded"))
    def test_ungrounded_ai_output_uses_safe_fallback(self, explanation_mock):
        payload = {**self.valid_search, "ai_mode": True}
        response = self.client.post("/api/flight-searches", json=payload)
        ai_result = response.get_json()["ai"]
        self.assertEqual(ai_result["status"], "guarded_fallback")
        self.assertIn("TR3", ai_result["explanation"])
        self.assertIn("1 stop", ai_result["explanation"])
        explanation_mock.assert_called_once()

    def test_grounding_validator_rejects_invented_stop_count(self):
        grounded = validate_grounded_explanation(
            "JQ11 is recommended and has 8 stops.",
            self.valid_search,
            TEST_FLIGHTS,
        )
        self.assertFalse(grounded)


if __name__ == "__main__":
    unittest.main()
