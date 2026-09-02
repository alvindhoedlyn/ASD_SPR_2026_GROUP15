import os
import sqlite3

from flask import Flask, jsonify, render_template, request


app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)


# =========================================================
# Database configuration
# =========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "budget.db")
SCHEMA_PATH = os.path.join(DATABASE_DIR, "schema.sql")


def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    os.makedirs(DATABASE_DIR, exist_ok=True)

    connection = get_db_connection()

    with open(SCHEMA_PATH, "r") as schema_file:
        connection.executescript(schema_file.read())

    connection.commit()
    connection.close()


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
        "student": "KeyuanGan"
    })


# =========================================================
# Expense CRUD
# =========================================================

# READ all expenses
@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    connection = get_db_connection()

    expenses = connection.execute(
        """
        SELECT expense_id,
               category,
               description,
               amount,
               expense_date
        FROM expenses
        ORDER BY expense_id DESC
        """
    ).fetchall()

    connection.close()

    return jsonify([dict(expense) for expense in expenses])


# CREATE expense
@app.route("/api/expenses", methods=["POST"])
def create_expense():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    category = data.get("category")
    description = data.get("description")
    amount = data.get("amount")
    expense_date = data.get("expense_date")

    if not category or not description or amount is None or not expense_date:
        return jsonify({
            "error": "category, description, amount and expense_date are required"
        }), 400

    try:
        amount = float(amount)

        if amount < 0:
            return jsonify({
                "error": "Amount cannot be negative"
            }), 400

    except (TypeError, ValueError):
        return jsonify({
            "error": "Amount must be a number"
        }), 400

    connection = get_db_connection()

    cursor = connection.execute(
        """
        INSERT INTO expenses (
            category,
            description,
            amount,
            expense_date
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            category,
            description,
            amount,
            expense_date
        )
    )

    connection.commit()

    expense_id = cursor.lastrowid

    connection.close()

    return jsonify({
        "message": "Expense created successfully",
        "expense_id": expense_id
    }), 201


# READ one expense
@app.route("/api/expenses/<int:expense_id>", methods=["GET"])
def get_expense(expense_id):
    connection = get_db_connection()

    expense = connection.execute(
        """
        SELECT expense_id,
               category,
               description,
               amount,
               expense_date
        FROM expenses
        WHERE expense_id = ?
        """,
        (expense_id,)
    ).fetchone()

    connection.close()

    if expense is None:
        return jsonify({
            "error": "Expense not found"
        }), 404

    return jsonify(dict(expense))


# UPDATE expense
@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def update_expense(expense_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    category = data.get("category")
    description = data.get("description")
    amount = data.get("amount")
    expense_date = data.get("expense_date")

    if not category or not description or amount is None or not expense_date:
        return jsonify({
            "error": "category, description, amount and expense_date are required"
        }), 400

    try:
        amount = float(amount)

        if amount < 0:
            return jsonify({
                "error": "Amount cannot be negative"
            }), 400

    except (TypeError, ValueError):
        return jsonify({
            "error": "Amount must be a number"
        }), 400

    connection = get_db_connection()

    existing_expense = connection.execute(
        """
        SELECT expense_id
        FROM expenses
        WHERE expense_id = ?
        """,
        (expense_id,)
    ).fetchone()

    if existing_expense is None:
        connection.close()

        return jsonify({
            "error": "Expense not found"
        }), 404

    connection.execute(
        """
        UPDATE expenses
        SET category = ?,
            description = ?,
            amount = ?,
            expense_date = ?
        WHERE expense_id = ?
        """,
        (
            category,
            description,
            amount,
            expense_date,
            expense_id
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Expense updated successfully"
    })


# DELETE expense
@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    connection = get_db_connection()

    existing_expense = connection.execute(
        """
        SELECT expense_id
        FROM expenses
        WHERE expense_id = ?
        """,
        (expense_id,)
    ).fetchone()

    if existing_expense is None:
        connection.close()

        return jsonify({
            "error": "Expense not found"
        }), 404

    connection.execute(
        """
        DELETE FROM expenses
        WHERE expense_id = ?
        """,
        (expense_id,)
    )

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Expense deleted successfully"
    })


# =========================================================
# Budget Settings
# =========================================================

# GET budget settings
@app.route("/api/budget", methods=["GET"])
def get_budget():
    connection = get_db_connection()

    budget = connection.execute(
        """
        SELECT id,
               total_budget,
               min_price,
               max_price
        FROM budget_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    connection.close()

    if budget is None:
        return jsonify({
            "total_budget": 0,
            "min_price": 0,
            "max_price": 0
        })

    return jsonify(dict(budget))


# CREATE / UPDATE budget settings
@app.route("/api/budget", methods=["POST"])
def save_budget():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    total_budget = data.get("total_budget")
    min_price = data.get("min_price")
    max_price = data.get("max_price")

    if (
        total_budget is None
        or min_price is None
        or max_price is None
    ):
        return jsonify({
            "error": "total_budget, min_price and max_price are required"
        }), 400

    try:
        total_budget = float(total_budget)
        min_price = float(min_price)
        max_price = float(max_price)

    except (TypeError, ValueError):
        return jsonify({
            "error": "Budget values must be numbers"
        }), 400

    if total_budget < 0:
        return jsonify({
            "error": "Total budget cannot be negative"
        }), 400

    if min_price < 0:
        return jsonify({
            "error": "Minimum price cannot be negative"
        }), 400

    if max_price < min_price:
        return jsonify({
            "error": "Maximum price must be greater than or equal to minimum price"
        }), 400

    connection = get_db_connection()

    existing_budget = connection.execute(
        """
        SELECT id
        FROM budget_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if existing_budget:
        connection.execute(
            """
            UPDATE budget_settings
            SET total_budget = ?,
                min_price = ?,
                max_price = ?
            WHERE id = ?
            """,
            (
                total_budget,
                min_price,
                max_price,
                existing_budget["id"]
            )
        )

    else:
        connection.execute(
            """
            INSERT INTO budget_settings (
                total_budget,
                min_price,
                max_price
            )
            VALUES (?, ?, ?)
            """,
            (
                total_budget,
                min_price,
                max_price
            )
        )

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Budget settings saved successfully"
    })


# =========================================================
# Budget Summary
# =========================================================

@app.route("/api/budget/summary", methods=["GET"])
def get_budget_summary():
    connection = get_db_connection()

    budget = connection.execute(
        """
        SELECT *
        FROM budget_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    total_spent = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        """
    ).fetchone()[0]

    connection.close()

    if budget is None:
        return jsonify({
            "total_budget": 0,
            "total_spent": round(total_spent, 2),
            "remaining_budget": 0,
            "min_price": 0,
            "max_price": 0
        })

    total_budget = budget["total_budget"]
    remaining_budget = total_budget - total_spent

    return jsonify({
        "total_budget": round(total_budget, 2),
        "total_spent": round(total_spent, 2),
        "remaining_budget": round(remaining_budget, 2),
        "min_price": round(budget["min_price"], 2),
        "max_price": round(budget["max_price"], 2)
    })


# =========================================================
# Start Application
# =========================================================

if __name__ == "__main__":
    init_database()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )