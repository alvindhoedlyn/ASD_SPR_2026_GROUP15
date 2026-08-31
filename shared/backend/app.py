import os
import sqlite3
import secrets
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder=None)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "instance", "app.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return response


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return "", 204


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if count == 0:
        seed_accounts(conn)

    conn.close()


def seed_accounts(conn):
    demo_accounts = [
        ("admin", "admin123", "admin"),
        ("client", "client123", "client"),
    ]
    for username, password, role in demo_accounts:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role)
        )
    conn.commit()

@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        conn.close()
        return jsonify({"error": "Invalid username or password"}), 401

    token = secrets.token_urlsafe(24)
    conn.execute(
        "INSERT INTO sessions (token, user_id, username, role) VALUES (?, ?, ?, ?)",
        (token, user["user_id"], user["username"], user["role"])
    )
    conn.commit()
    conn.close()

    return jsonify({"token": token, "username": user["username"], "role": user["role"]})


@app.route("/api/verify-session", methods=["GET"])
def verify_session():
    token = request.args.get("token", "")
    conn = get_db()
    session = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    conn.close()

    if session is None:
        return jsonify({"error": "Invalid or expired session"}), 401

    return jsonify({"username": session["username"], "role": session["role"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    data = request.get_json() or {}
    token = data.get("token", "")
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return jsonify({"logged_out": True})

@app.route("/api/users", methods=["POST"])
def create_user():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "client")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "username already exists"}), 409
    conn.close()
    return jsonify({"created": username}), 201


@app.route("/api/users", methods=["GET"])
def list_users():
    conn = get_db()
    rows = conn.execute("SELECT user_id, username, role, created_at FROM users").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": user_id})


@app.route("/health")
def health():
    return {"status": "ok", "service": "shared-auth"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=80)