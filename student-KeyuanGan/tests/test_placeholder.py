import os
import sys
import unittest
from unittest.mock import patch


# Add backend directory to Python path
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "backend"
        )
    )
)


from app import app


class BudgetTrackerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()


    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(
            response.status_code,
            200
        )

        data = response.get_json()

        self.assertEqual(
            data["status"],
            "ok"
        )

        self.assertEqual(
            data["student"],
            "KeyuanGan"
        )

        self.assertEqual(
            data["service"],
            "backend"
        )


    @patch("app.db_get_expenses")
    def test_get_expenses(self, mock_get_expenses):

        mock_get_expenses.return_value = [
            {
                "expense_id": i,
                "category": "Food",
                "description": f"Expense {i}",
                "amount": 10.0,
                "expense_date": "2026-09-05"
            }
            for i in range(1, 11)
        ]

        response = self.client.get(
            "/api/expenses"
        )

        self.assertEqual(
            response.status_code,
            200
        )

        data = response.get_json()

        self.assertIsInstance(
            data,
            list
        )

        self.assertGreaterEqual(
            len(data),
            10
        )

        mock_get_expenses.assert_called_once()


    @patch("app.db_create_expense")
    def test_create_expense(
        self,
        mock_create_expense
    ):

        mock_create_expense.return_value = {
            "message": "Expense created successfully",
            "expense_id": 11
        }

        response = self.client.post(
            "/api/expenses",
            json={
                "category": "Food",
                "description": "Test expense",
                "amount": 15.50,
                "expense_date": "2026-09-05"
            }
        )

        self.assertEqual(
            response.status_code,
            201
        )

        data = response.get_json()

        self.assertIn(
            "expense_id",
            data
        )

        self.assertEqual(
            data["expense_id"],
            11
        )

        mock_create_expense.assert_called_once()


    @patch("app.db_create_expense")
    def test_invalid_expense_amount(
        self,
        mock_create_expense
    ):

        response = self.client.post(
            "/api/expenses",
            json={
                "category": "Food",
                "description": "Invalid expense",
                "amount": -10,
                "expense_date": "2026-09-05"
            }
        )

        self.assertEqual(
            response.status_code,
            400
        )

        mock_create_expense.assert_not_called()


    @patch("app.db_get_expenses")
    @patch("app.db_get_budget")
    def test_budget_summary(
        self,
        mock_get_budget,
        mock_get_expenses
    ):

        mock_get_budget.return_value = {
            "total_budget": 5000,
            "min_price": 1000,
            "max_price": 2500
        }

        mock_get_expenses.return_value = [
            {
                "expense_id": 1,
                "category": "Transport",
                "description": "Flight",
                "amount": 500.0,
                "expense_date": "2026-09-05"
            },
            {
                "expense_id": 2,
                "category": "Food",
                "description": "Dinner",
                "amount": 100.0,
                "expense_date": "2026-09-05"
            }
        ]

        response = self.client.get(
            "/api/budget/summary"
        )

        self.assertEqual(
            response.status_code,
            200
        )

        data = response.get_json()

        self.assertEqual(
            data["total_budget"],
            5000
        )

        self.assertEqual(
            data["total_spent"],
            600.0
        )

        self.assertEqual(
            data["remaining_budget"],
            4400.0
        )

        self.assertEqual(
            data["min_price"],
            1000
        )

        self.assertEqual(
            data["max_price"],
            2500
        )


    @patch("app.run_budget_agent")
    def test_ai_budget_advice(
        self,
        mock_run_budget_agent
    ):

        mock_run_budget_agent.return_value = {
            "summary": {
                "total_budget": 5000.0,
                "total_spent": 1323.5,
                "remaining_budget": 3676.5,
                "spending_percentage": 26.5,
                "highest_category": "Transport",
                "highest_category_amount": 657.0,
                "min_price": 1000.0,
                "max_price": 2500.0
            },

            "advice":
                "Reduce unnecessary transport expenses.",

            "trace": [
                {
                    "stage": "Plan",
                    "detail":
                        "Analyse current budget and expenses."
                },
                {
                    "stage": "Act",
                    "detail":
                        "Retrieve budget and expense data."
                },
                {
                    "stage": "Observe",
                    "detail":
                        "Calculate spending and remaining budget."
                },
                {
                    "stage": "Adapt",
                    "detail":
                        "Generate grounded advice using Qwen."
                }
            ]
        }

        response = self.client.get(
            "/api/ai/budget-advice"
        )

        self.assertEqual(
            response.status_code,
            200
        )

        data = response.get_json()

        self.assertIn(
            "advice",
            data
        )

        self.assertIn(
            "summary",
            data
        )

        self.assertIn(
            "trace",
            data
        )

        stages = [
            step["stage"]
            for step in data["trace"]
        ]

        self.assertEqual(
            stages,
            [
                "Plan",
                "Act",
                "Observe",
                "Adapt"
            ]
        )

        mock_run_budget_agent.assert_called_once()


    @patch("app.db_delete_expense")
    def test_delete_expense(
        self,
        mock_delete_expense
    ):

        mock_delete_expense.return_value = {
            "message":
                "Expense deleted successfully"
        }

        response = self.client.delete(
            "/api/expenses/10"
        )

        self.assertEqual(
            response.status_code,
            200
        )

        data = response.get_json()

        self.assertIn(
            "message",
            data
        )

        mock_delete_expense.assert_called_once_with(
            10
        )


if __name__ == "__main__":
    unittest.main()