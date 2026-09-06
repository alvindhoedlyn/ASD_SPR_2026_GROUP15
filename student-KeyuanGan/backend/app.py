from flask import Flask, jsonify, render_template, request

from agentic_loop import run_budget_agent

from database_client import (
    get_expenses as db_get_expenses,
    get_expense as db_get_expense,
    create_expense as db_create_expense,
    update_expense as db_update_expense,
    delete_expense as db_delete_expense,
    get_budget as db_get_budget,
    save_budget as db_save_budget,
)


app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)


# =========================================================
# Home
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# Health Check
# =========================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "student": "KeyuanGan",
        "service": "backend"
    })


# =========================================================
# Validation Helpers
# =========================================================

def validate_expense_data(data):
    """
    Validate expense request data.

    Returns:
        (validated_data, error_message)
    """

    if not data:
        return None, "Request body is required"

    category = data.get("category")
    description = data.get("description")
    amount = data.get("amount")
    expense_date = data.get("expense_date")

    if (
        not category
        or not description
        or amount is None
        or not expense_date
    ):
        return (
            None,
            "category, description, amount and expense_date are required"
        )

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None, "Amount must be a number"

    if amount < 0:
        return None, "Amount cannot be negative"

    return {
        "category": category,
        "description": description,
        "amount": amount,
        "expense_date": expense_date
    }, None


def validate_budget_data(data):
    """
    Validate budget request data.

    Returns:
        (validated_data, error_message)
    """

    if not data:
        return None, "Request body is required"

    total_budget = data.get("total_budget")
    min_price = data.get("min_price")
    max_price = data.get("max_price")

    if (
        total_budget is None
        or min_price is None
        or max_price is None
    ):
        return (
            None,
            "total_budget, min_price and max_price are required"
        )

    try:
        total_budget = float(total_budget)
        min_price = float(min_price)
        max_price = float(max_price)
    except (TypeError, ValueError):
        return None, "Budget values must be numbers"

    if total_budget < 0:
        return None, "Total budget cannot be negative"

    if min_price < 0:
        return None, "Minimum price cannot be negative"

    if max_price < min_price:
        return (
            None,
            "Maximum price must be greater than or equal to minimum price"
        )

    return {
        "total_budget": total_budget,
        "min_price": min_price,
        "max_price": max_price
    }, None


# =========================================================
# Expense CRUD
# =========================================================

# READ all expenses
@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    try:
        expenses = db_get_expenses()

        return jsonify(expenses)

    except Exception as error:
        return jsonify({
            "error": "Database service unavailable",
            "details": str(error)
        }), 503


# READ one expense
@app.route("/api/expenses/<int:expense_id>", methods=["GET"])
def get_expense(expense_id):
    try:
        expense = db_get_expense(expense_id)

        return jsonify(expense)

    except Exception as error:
        return jsonify({
            "error": "Unable to retrieve expense",
            "details": str(error)
        }), 503


# CREATE expense
@app.route("/api/expenses", methods=["POST"])
def create_expense():
    data = request.get_json(silent=True)

    validated_data, error = validate_expense_data(data)

    if error:
        return jsonify({
            "error": error
        }), 400

    try:
        result = db_create_expense(validated_data)

        return jsonify(result), 201

    except Exception as error:
        return jsonify({
            "error": "Unable to create expense",
            "details": str(error)
        }), 503


# UPDATE expense
@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def update_expense(expense_id):
    data = request.get_json(silent=True)

    validated_data, error = validate_expense_data(data)

    if error:
        return jsonify({
            "error": error
        }), 400

    try:
        result = db_update_expense(
            expense_id,
            validated_data
        )

        return jsonify(result)

    except Exception as error:
        return jsonify({
            "error": "Unable to update expense",
            "details": str(error)
        }), 503


# DELETE expense
@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    try:
        db_delete_expense(expense_id)

        return jsonify({
            "message": "Expense deleted successfully"
        })

    except Exception as error:
        return jsonify({
            "error": "Unable to delete expense",
            "details": str(error)
        }), 503


# =========================================================
# Budget Settings
# =========================================================

# READ budget
@app.route("/api/budget", methods=["GET"])
def get_budget():
    try:
        budget = db_get_budget()

        return jsonify(budget)

    except Exception as error:
        return jsonify({
            "error": "Unable to retrieve budget",
            "details": str(error)
        }), 503


# CREATE / UPDATE budget
@app.route("/api/budget", methods=["POST"])
def save_budget():
    data = request.get_json(silent=True)

    validated_data, error = validate_budget_data(data)

    if error:
        return jsonify({
            "error": error
        }), 400

    try:
        result = db_save_budget(validated_data)

        return jsonify(result)

    except Exception as error:
        return jsonify({
            "error": "Unable to save budget",
            "details": str(error)
        }), 503


# =========================================================
# Budget Summary
# =========================================================

@app.route("/api/budget/summary", methods=["GET"])
def get_budget_summary():
    """
    Calculate the budget summary using data returned
    by the Database Microservice.

    The Backend does not access SQLite directly.
    """

    try:
        budget = db_get_budget()
        expenses = db_get_expenses()

        total_budget = float(
            budget.get("total_budget", 0) or 0
        )

        min_price = float(
            budget.get("min_price", 0) or 0
        )

        max_price = float(
            budget.get("max_price", 0) or 0
        )

        total_spent = sum(
            float(expense.get("amount", 0) or 0)
            for expense in expenses
        )

        remaining_budget = (
            total_budget - total_spent
        )

        return jsonify({
            "total_budget": round(
                total_budget,
                2
            ),
            "total_spent": round(
                total_spent,
                2
            ),
            "remaining_budget": round(
                remaining_budget,
                2
            ),
            "min_price": round(
                min_price,
                2
            ),
            "max_price": round(
                max_price,
                2
            )
        })

    except Exception as error:
        return jsonify({
            "error": "Unable to calculate budget summary",
            "details": str(error)
        }), 503


# =========================================================
# Agentic AI Budget Advisor
# =========================================================

@app.route(
    "/api/ai/budget-advice",
    methods=["GET"]
)
def ai_budget_advice():
    """
    Run the Budget Advisor Agent.

    Agentic flow:
        PLAN
        ACT
        OBSERVE
        ADAPT
    """

    try:
        result = run_budget_agent()

        return jsonify(result), 200

    except Exception as error:
        return jsonify({
            "error": "Unable to generate budget advice",
            "details": str(error)
        }), 500


# =========================================================
# Error Handlers
# =========================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Resource not found"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method not allowed"
    }), 405


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "error": "Internal server error"
    }), 500


# =========================================================
# Application Start
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )