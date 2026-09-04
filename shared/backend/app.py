import os
import secrets
import requests
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE_API_URL = os.environ.get("DATABASE_API_URL", "http://shared-database:6000")
PORT = int(os.environ.get("PORT", 5000))


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return response


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return "", 204


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    resp = requests.get(f"{DATABASE_API_URL}/users", params={"username": username})
    if resp.status_code != 200:
        return jsonify({"error": "Invalid username or password"}), 401

    user = resp.json()
    if not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = secrets.token_urlsafe(24)
    session_resp = requests.post(
        f"{DATABASE_API_URL}/sessions",
        json={
            "token": token,
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"],
        },
    )
    if session_resp.status_code != 201:
        return jsonify({"error": "Could not create session"}), 500

    return jsonify({"token": token, "username": user["username"], "role": user["role"]})


@app.route("/api/verify-session", methods=["GET"])
def verify_session():
    token = request.args.get("token", "")
    resp = requests.get(f"{DATABASE_API_URL}/sessions/{token}")
    if resp.status_code != 200:
        return jsonify({"error": "Invalid or expired session"}), 401

    session = resp.json()
    return jsonify({"username": session["username"], "role": session["role"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    data = request.get_json() or {}
    token = data.get("token", "")
    if token:
        try:
            requests.delete(f"{DATABASE_API_URL}/sessions/{token}")
        except requests.RequestException:
            pass  # best-effort logout, mirrors previous client-side behaviour
    return jsonify({"logged_out": True})


@app.route("/api/users", methods=["POST"])
def create_user():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "client")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    resp = requests.post(
        f"{DATABASE_API_URL}/users",
        json={
            "username": username,
            "password_hash": generate_password_hash(password),
            "role": role,
        },
    )
    if resp.status_code == 409:
        return jsonify({"error": "username already exists"}), 409
    if resp.status_code != 201:
        return jsonify({"error": "Could not create user"}), 500

    return jsonify({"created": username}), 201


@app.route("/api/users", methods=["GET"])
def list_users():
    resp = requests.get(f"{DATABASE_API_URL}/users")
    return jsonify(resp.json()), resp.status_code


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    resp = requests.delete(f"{DATABASE_API_URL}/users/{user_id}")
    return jsonify(resp.json()), resp.status_code


@app.route("/health")
def health():
    return {"status": "ok", "service": "shared-api"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
