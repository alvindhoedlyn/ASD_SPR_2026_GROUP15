import os
import sys
import unittest

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "backend"
        )
    )
)

from app import app, init_database


class BudgetTrackerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_database()
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertEqual(data["status"], "ok")

    def test_get_expenses(self):
        response = self.client.get("/api/expenses")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 10)

    def test_create_expense(self):
        response = self.client.post(
            "/api/expenses",
            json={
                "category": "Food",
                "description": "Test expense",
                "amount": 15.50,
                "expense_date": "2026-09-05"
            }
        )

        self.assertEqual(response.status_code, 201)

        data = response.get_json()

        self.assertIn("expense_id", data)

    def test_invalid_expense_amount(self):
        response = self.client.post(
            "/api/expenses",
            json={
                "category": "Food",
                "description": "Invalid expense",
                "amount": -10,
                "expense_date": "2026-09-05"
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_budget_summary(self):
        response = self.client.get("/api/budget/summary")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertIn("total_budget", data)
        self.assertIn("total_spent", data)
        self.assertIn("remaining_budget", data)
        self.assertIn("min_price", data)
        self.assertIn("max_price", data)


if __name__ == "__main__":
    unittest.main()
