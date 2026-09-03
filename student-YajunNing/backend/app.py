import os
from datetime import date

import requests
from flask import Flask, jsonify, render_template, request

from agentic_loop import run_flight_agent
from database_client import database_request
from flights import build_grounded_fallback
from llm_client import generate_ai_explanation

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://shared-frontend")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return {"status": "ok", "student": "5"}


ALLOWED_PREFERENCES = {"best_overall", "cheapest", "fastest", "fewest_stops"}
ORIGIN_ALIASES = {"SYD", "SYDNEY", "SYDNEY (SYD)"}
DESTINATION_ALIASES = {"NRT", "HND", "TOKYO", "TOKYO (NRT)", "TOKYO (HND)"}


def _validate_search(payload):
    required = ("origin", "destination", "departure_date", "max_budget", "preference")
    missing = [field for field in required if not str(payload.get(field, "")).strip()]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"

    try:
        departure_date = date.fromisoformat(payload["departure_date"])
    except (TypeError, ValueError):
        return "departure_date must use YYYY-MM-DD format"

    return_date = payload.get("return_date")
    if return_date:
        try:
            parsed_return_date = date.fromisoformat(return_date)
        except (TypeError, ValueError):
            return "return_date must use YYYY-MM-DD format"
        if parsed_return_date < departure_date:
            return "return_date cannot be before departure_date"

    try:
        if float(payload["max_budget"]) <= 0:
            return "max_budget must be greater than zero"
    except (TypeError, ValueError):
        return "max_budget must be a number"

    if payload["preference"] not in ALLOWED_PREFERENCES:
        return "preference is not supported"

    return None


def _is_enabled(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def verify_request_session():
    token = request.headers.get("X-Session-Token", "").strip()
    if not token:
        return None, (jsonify({"error": "Login required"}), 401)

    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/api/verify-session",
            params={"token": token},
            timeout=5,
        )
    except requests.RequestException:
        return None, (jsonify({"error": "Login service is unavailable"}), 503)

    if response.status_code != 200:
        return None, (jsonify({"error": "Invalid or expired login session"}), 401)
    return response.json(), None


@app.post("/api/flight-searches")
def create_flight_search():
    payload = request.get_json(silent=True) or {}
    validation_error = _validate_search(payload)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    origin = str(payload["origin"]).strip().upper()
    destination = str(payload["destination"]).strip().upper()
    if origin not in ORIGIN_ALIASES or destination not in DESTINATION_ALIASES:
        return jsonify({
            "recommendations": [],
            "message": "The current flight catalogue supports Sydney to Tokyo only.",
            "total_matches": 0,
            "ai": {"requested": _is_enabled(payload.get("ai_mode")), "status": "no_results", "explanation": None},
            "agentic_loop": {
                "adapted": False,
                "trace": [
                    {"stage": "Plan", "detail": "Interpret the requested route and travel constraints."},
                    {"stage": "Act", "detail": "Check whether the route is supported by the catalogue."},
                    {"stage": "Observe", "detail": "The requested route is outside the Sydney-to-Tokyo Release 0 scope."},
                    {"stage": "Adapt", "detail": "Return no result rather than inventing unavailable flight data."},
                ],
            },
        })

    max_budget = float(payload["max_budget"])
    preference = payload["preference"]
    search = {
        "origin": "SYD",
        "destination": "Tokyo",
        "departure_date": payload["departure_date"],
        "return_date": payload.get("return_date") or None,
        "max_budget": max_budget,
        "preference": preference,
    }

    try:
        agent_result = run_flight_agent(search)
    except requests.RequestException:
        return jsonify({"error": "Flight database service is unavailable"}), 503

    recommendations = agent_result["recommendations"]
    ai_requested = _is_enabled(payload.get("ai_mode"))
    ai_status = "not_requested"
    ai_explanation = None

    if ai_requested and recommendations:
        try:
            ai_explanation = generate_ai_explanation(
                search,
                recommendations,
                agent_result["trace"],
            )
            ai_status = "ready" if ai_explanation else "unavailable"
        except Exception:
            ai_explanation = build_grounded_fallback(search, recommendations)
            ai_status = "guarded_fallback"
    elif ai_requested:
        ai_status = "no_results"

    return jsonify({
        "message": agent_result["message"],
        "recommendations": recommendations,
        "search": search,
        "available_count": agent_result["available_count"],
        "returned_count": len(recommendations),
        "agentic_loop": {
            "adapted": agent_result["adapted"],
            "trace": agent_result["trace"],
        },
        "ai": {
            "requested": ai_requested,
            "status": ai_status,
            "explanation": ai_explanation,
        },
    })


def proxy_database_request(method, path, params=None, json_body=None):
    try:
        response = database_request(
            method,
            path,
            params=params if params is not None else (request.args if method in {"GET", "DELETE"} else None),
            json=json_body if json_body is not None else (request.get_json(silent=True) if method in {"POST", "PUT"} else None),
        )
    except requests.RequestException:
        return jsonify({"error": "Flight database service is unavailable"}), 503

    if response.status_code == 204:
        return "", 204
    return jsonify(response.json()), response.status_code


@app.get("/api/flights")
def list_flights():
    return proxy_database_request("GET", "/flights")


@app.get("/api/flights/<int:flight_id>")
def get_flight(flight_id):
    return proxy_database_request("GET", f"/flights/{flight_id}")


@app.get("/api/session")
def get_current_session():
    session, error = verify_request_session()
    if error:
        return error
    return jsonify(session)


@app.get("/api/saved-flights")
def list_saved_flights():
    session, error = verify_request_session()
    if error:
        return error
    return proxy_database_request("GET", "/saved-flights", params={"username": session["username"]})


@app.get("/api/saved-flights/<int:saved_flight_id>")
def get_saved_flight(saved_flight_id):
    session, error = verify_request_session()
    if error:
        return error
    return proxy_database_request(
        "GET",
        f"/saved-flights/{saved_flight_id}",
        params={"username": session["username"]},
    )


@app.post("/api/saved-flights")
def create_saved_flight():
    session, error = verify_request_session()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    payload["username"] = session["username"]
    return proxy_database_request("POST", "/saved-flights", json_body=payload)


@app.put("/api/saved-flights/<int:saved_flight_id>")
def update_saved_flight(saved_flight_id):
    session, error = verify_request_session()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    payload["username"] = session["username"]
    return proxy_database_request("PUT", f"/saved-flights/{saved_flight_id}", json_body=payload)


@app.delete("/api/saved-flights/<int:saved_flight_id>")
def delete_saved_flight(saved_flight_id):
    session, error = verify_request_session()
    if error:
        return error
    return proxy_database_request(
        "DELETE",
        f"/saved-flights/{saved_flight_id}",
        params={"username": session["username"]},
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
