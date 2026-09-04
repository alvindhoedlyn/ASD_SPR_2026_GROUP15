import os
import sqlite3
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash

app = Flask(__name__)

DATABASE_PATH = os.environ.get(
    "DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "app.db")
)
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")
PORT = int(os.environ.get("PORT", 6000))


def get_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if count == 0:
        demo_accounts = [
            ("admin", "admin123", "admin"),
            ("client", "client123", "client"),
        ]
        for username, password, role in demo_accounts:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), role),
            )
        conn.commit()

    conn.close()


@app.route("/health")
def health():
    return {"status": "ok", "service": "shared-database"}


# ---------------------------------------------------------------- users ----

@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json() or {}
    username = data.get("username")
    password_hash = data.get("password_hash")
    role = data.get("role", "client")

    if not username or not password_hash:
        return jsonify({"error": "username and password_hash are required"}), 400

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "username already exists"}), 409
    conn.close()
    return jsonify({"user_id": user_id, "username": username, "role": role}), 201


@app.route("/users", methods=["GET"])
def list_users():
    # GET /users            -> list of all users (no password_hash)
    # GET /users?username=x -> single full user row (used by login), 404 if missing
    username = request.args.get("username")
    conn = get_db()
    if username:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()
        if row is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(dict(row))

    rows = conn.execute(
        "SELECT user_id, username, role, created_at FROM users"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": user_id})


# ------------------------------------------------------------ sessions ----

@app.route("/sessions", methods=["POST"])
def create_session():
    data = request.get_json() or {}
    token = data.get("token")
    user_id = data.get("user_id")
    username = data.get("username")
    role = data.get("role")

    if not all([token, user_id, username, role]):
        return jsonify({"error": "token, user_id, username, role are required"}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (token, user_id, username, role) VALUES (?, ?, ?, ?)",
        (token, user_id, username, role),
    )
    conn.commit()
    conn.close()
    return jsonify({"token": token}), 201


@app.route("/sessions/<token>", methods=["GET"])
def get_session(token):
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    if session is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(session))


@app.route("/sessions/<token>", methods=["DELETE"])
def delete_session(token):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": token})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT)
