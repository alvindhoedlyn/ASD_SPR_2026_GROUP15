import os
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
DATABASE_PATH = os.path.join(DATA_DIR, "budget.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    os.makedirs(DATA_DIR, exist_ok=True)

    connection = get_connection()

    with open(SCHEMA_PATH, "r") as schema_file:
        connection.executescript(schema_file.read())

    connection.commit()
    connection.close()


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "KeyuanGan-budget-database"
    })


# =========================================================
# Expense CRUD
# =========================================================

@app.get("/expenses")
def get_expenses():
    connection = get_connection()

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


@app.get("/expenses/<int:expense_id>")
def get_expense(expense_id):
    connection = get_connection()

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
        return jsonify({"error": "Expense not found"}), 404

    return jsonify(dict(expense))


@app.post("/expenses")
def create_expense():
    payload = request.get_json(silent=True) or {}

    category = str(payload.get("category") or "").strip()
    description = str(payload.get("description") or "").strip()
    expense_date = str(payload.get("expense_date") or "").strip()

    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "Amount must be a number"}), 400

    if not category or not description or not expense_date:
        return jsonify({
            "error": "category, description and expense_date are required"
        }), 400

    if amount < 0:
        return jsonify({"error": "Amount cannot be negative"}), 400

    connection = get_connection()

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
        (category, description, amount, expense_date)
    )

    connection.commit()
    expense_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "message": "Expense created successfully",
        "expense_id": expense_id
    }), 201


@app.put("/expenses/<int:expense_id>")
def update_expense(expense_id):
    payload = request.get_json(silent=True) or {}

    category = str(payload.get("category") or "").strip()
    description = str(payload.get("description") or "").strip()
    expense_date = str(payload.get("expense_date") or "").strip()

    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "Amount must be a number"}), 400

    if not category or not description or not expense_date:
        return jsonify({
            "error": "category, description and expense_date are required"
        }), 400

    if amount < 0:
        return jsonify({"error": "Amount cannot be negative"}), 400

    connection = get_connection()

    cursor = connection.execute(
        """
        UPDATE expenses
        SET category = ?,
            description = ?,
            amount = ?,
            expense_date = ?
        WHERE expense_id = ?
        """,
        (category, description, amount, expense_date, expense_id)
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "Expense not found"}), 404

    return jsonify({"message": "Expense updated successfully"})


@app.delete("/expenses/<int:expense_id>")
def delete_expense(expense_id):
    connection = get_connection()

    cursor = connection.execute(
        """
        DELETE FROM expenses
        WHERE expense_id = ?
        """,
        (expense_id,)
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "Expense not found"}), 404

    return "", 204


# =========================================================
# Budget Settings
# =========================================================

@app.get("/budget")
def get_budget():
    connection = get_connection()

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


@app.post("/budget")
def save_budget():
    payload = request.get_json(silent=True) or {}

    try:
        total_budget = float(payload.get("total_budget"))
        min_price = float(payload.get("min_price"))
        max_price = float(payload.get("max_price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Budget values must be numbers"}), 400

    if total_budget < 0:
        return jsonify({"error": "Total budget cannot be negative"}), 400

    if min_price < 0:
        return jsonify({"error": "Minimum price cannot be negative"}), 400

    if max_price < min_price:
        return jsonify({
            "error": "Maximum price must be greater than or equal to minimum price"
        }), 400

    connection = get_connection()

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
            (total_budget, min_price, max_price)
        )

    connection.commit()
    connection.close()

    return jsonify({"message": "Budget settings saved successfully"})


# =========================================================
# Budget Summary
# =========================================================

@app.get("/budget/summary")
def get_budget_summary():
    connection = get_connection()

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

    category_rows = connection.execute(
        """
        SELECT category,
               ROUND(SUM(amount), 2) AS total
        FROM expenses
        GROUP BY category
        ORDER BY total DESC
        """
    ).fetchall()

    connection.close()

    categories = {
        row["category"]: row["total"]
        for row in category_rows
    }

    if budget is None:
        return jsonify({
            "total_budget": 0,
            "total_spent": round(total_spent, 2),
            "remaining_budget": 0,
            "min_price": 0,
            "max_price": 0,
            "category_totals": categories
        })

    total_budget = budget["total_budget"]

    return jsonify({
        "total_budget": round(total_budget, 2),
        "total_spent": round(total_spent, 2),
        "remaining_budget": round(total_budget - total_spent, 2),
        "min_price": round(budget["min_price"], 2),
        "max_price": round(budget["max_price"], 2),
        "category_totals": categories
    })


if __name__ == "__main__":
    init_database()
    app.run(host="0.0.0.0", port=5001)