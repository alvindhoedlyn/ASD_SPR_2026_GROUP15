"""SQLite owner and CRUD API for the Flight Recommender."""

import os
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request

from init_db import initialize_database


app = Flask(__name__)
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "data" / "flights.db"
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
FLIGHT_FIELDS = (
    "airline",
    "flight_number",
    "origin",
    "destination",
    "departure_time",
    "arrival_time",
    "price_aud",
    "duration_minutes",
    "stops",
)
SAVED_FLIGHT_STATUSES = {"considering", "booked", "cancelled"}

initialize_database(DATABASE_PATH)


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def validate_username(value):
    username = str(value or "").strip()
    if not username:
        return None, "username is required"
    if len(username) > 80:
        return None, "username must be 80 characters or fewer"
    return username, None


def validate_iso_date(value, field_name, required=False):
    clean = str(value or "").strip()
    if not clean:
        return (None, f"{field_name} is required") if required else (None, None)
    try:
        date.fromisoformat(clean)
    except ValueError:
        return None, f"{field_name} must use YYYY-MM-DD format"
    return clean, None


def saved_flight_query():
    return """
        SELECT
            saved_flights.*,
            flights.airline,
            flights.flight_number,
            flights.origin,
            flights.destination,
            flights.departure_time,
            flights.arrival_time,
            flights.price_aud,
            flights.duration_minutes,
            flights.stops
        FROM saved_flights
        JOIN flights ON flights.id = saved_flights.flight_id
    """


def get_saved_flight_record(saved_flight_id, username):
    connection = get_connection()
    saved_flight = connection.execute(
        saved_flight_query() + " WHERE saved_flights.id = ? AND saved_flights.username = ?",
        (saved_flight_id, username),
    ).fetchone()
    connection.close()
    return dict(saved_flight) if saved_flight else None


def validate_flight(payload):
    missing = [field for field in FLIGHT_FIELDS if payload.get(field) in (None, "")]
    if missing:
        return None, f"Missing required fields: {', '.join(missing)}"

    clean = {field: payload[field] for field in FLIGHT_FIELDS}
    clean["airline"] = str(clean["airline"]).strip()
    clean["flight_number"] = str(clean["flight_number"]).strip().upper()
    clean["origin"] = str(clean["origin"]).strip().upper()
    clean["destination"] = str(clean["destination"]).strip().upper()

    try:
        clean["price_aud"] = float(clean["price_aud"])
        clean["duration_minutes"] = int(clean["duration_minutes"])
        clean["stops"] = int(clean["stops"])
    except (TypeError, ValueError):
        return None, "price_aud, duration_minutes, and stops must be numeric"

    if clean["price_aud"] <= 0 or clean["duration_minutes"] <= 0 or clean["stops"] < 0:
        return None, "Flight price and duration must be positive, and stops cannot be negative"

    return clean, None


@app.get("/health")
def health():
    connection = get_connection()
    flight_count = connection.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    saved_flight_count = connection.execute("SELECT COUNT(*) FROM saved_flights").fetchone()[0]
    connection.close()
    return jsonify({
        "service": "flight-database-service",
        "status": "ok",
        "storage": "SQLite",
        "flight_count": flight_count,
        "saved_flight_count": saved_flight_count,
    })


@app.get("/flights")
def list_flights():
    clauses = []
    values = []

    for field in ("origin", "destination"):
        value = request.args.get(field, "").strip().upper()
        if value:
            clauses.append(f"{field} = ?")
            values.append(value)

    max_budget = request.args.get("max_budget", "").strip()
    if max_budget:
        try:
            values.append(float(max_budget))
        except ValueError:
            return jsonify({"error": "max_budget must be a number"}), 400
        clauses.append("price_aud <= ?")

    query = "SELECT * FROM flights"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id"

    connection = get_connection()
    flights = connection.execute(query, values).fetchall()
    connection.close()
    return jsonify([dict(flight) for flight in flights])


@app.get("/flights/<int:flight_id>")
def get_flight(flight_id):
    connection = get_connection()
    flight = connection.execute("SELECT * FROM flights WHERE id = ?", (flight_id,)).fetchone()
    connection.close()
    if flight is None:
        return jsonify({"error": "Flight not found"}), 404
    return jsonify(dict(flight))


@app.post("/flights")
def create_flight():
    clean, error = validate_flight(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400

    placeholders = ", ".join("?" for _ in FLIGHT_FIELDS)
    connection = get_connection()
    try:
        cursor = connection.execute(
            f"INSERT INTO flights ({', '.join(FLIGHT_FIELDS)}) VALUES ({placeholders})",
            [clean[field] for field in FLIGHT_FIELDS],
        )
        connection.commit()
        flight_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        connection.close()
        return jsonify({"error": "flight_number must be unique"}), 409
    connection.close()
    return get_flight(flight_id), 201


@app.put("/flights/<int:flight_id>")
def update_flight(flight_id):
    clean, error = validate_flight(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400

    assignments = ", ".join(f"{field} = ?" for field in FLIGHT_FIELDS)
    connection = get_connection()
    try:
        cursor = connection.execute(
            f"UPDATE flights SET {assignments} WHERE id = ?",
            [clean[field] for field in FLIGHT_FIELDS] + [flight_id],
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.close()
        return jsonify({"error": "flight_number must be unique"}), 409
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "Flight not found"}), 404
    return get_flight(flight_id)


@app.delete("/flights/<int:flight_id>")
def delete_flight(flight_id):
    connection = get_connection()
    cursor = connection.execute("DELETE FROM flights WHERE id = ?", (flight_id,))
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Flight not found"}), 404
    return "", 204


@app.get("/saved-flights")
def list_saved_flights():
    username, error = validate_username(request.args.get("username"))
    if error:
        return jsonify({"error": error}), 400

    connection = get_connection()
    saved_flights = connection.execute(
        saved_flight_query()
        + " WHERE saved_flights.username = ? ORDER BY saved_flights.updated_at DESC, saved_flights.id DESC",
        (username,),
    ).fetchall()
    connection.close()
    return jsonify([dict(saved_flight) for saved_flight in saved_flights])


@app.get("/saved-flights/<int:saved_flight_id>")
def get_saved_flight(saved_flight_id):
    username, error = validate_username(request.args.get("username"))
    if error:
        return jsonify({"error": error}), 400
    saved_flight = get_saved_flight_record(saved_flight_id, username)
    if saved_flight is None:
        return jsonify({"error": "Saved flight not found"}), 404
    return jsonify(saved_flight)


@app.post("/saved-flights")
def create_saved_flight():
    payload = request.get_json(silent=True) or {}
    username, error = validate_username(payload.get("username"))
    if error:
        return jsonify({"error": error}), 400

    try:
        flight_id = int(payload.get("flight_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "flight_id must be an integer"}), 400

    departure_date, error = validate_iso_date(payload.get("departure_date"), "departure_date", required=True)
    if error:
        return jsonify({"error": error}), 400
    return_date, error = validate_iso_date(payload.get("return_date"), "return_date")
    if error:
        return jsonify({"error": error}), 400
    if return_date and return_date < departure_date:
        return jsonify({"error": "return_date cannot be before departure_date"}), 400

    connection = get_connection()
    flight_exists = connection.execute("SELECT 1 FROM flights WHERE id = ?", (flight_id,)).fetchone()
    if not flight_exists:
        connection.close()
        return jsonify({"error": "Flight not found"}), 404

    duplicate = connection.execute(
        """
        SELECT id FROM saved_flights
        WHERE username = ? AND flight_id = ? AND departure_date = ?
          AND COALESCE(return_date, '') = COALESCE(?, '')
        """,
        (username, flight_id, departure_date, return_date),
    ).fetchone()
    if duplicate:
        connection.close()
        return jsonify({"error": "This flight is already saved for these travel dates"}), 409

    cursor = connection.execute(
        """
        INSERT INTO saved_flights (username, flight_id, departure_date, return_date)
        VALUES (?, ?, ?, ?)
        """,
        (username, flight_id, departure_date, return_date),
    )
    connection.commit()
    saved_flight_id = cursor.lastrowid
    connection.close()
    return jsonify(get_saved_flight_record(saved_flight_id, username)), 201


@app.put("/saved-flights/<int:saved_flight_id>")
def update_saved_flight(saved_flight_id):
    payload = request.get_json(silent=True) or {}
    username, error = validate_username(payload.get("username"))
    if error:
        return jsonify({"error": error}), 400

    status = str(payload.get("status") or "").strip().lower()
    if status not in SAVED_FLIGHT_STATUSES:
        return jsonify({"error": "status must be considering, booked, or cancelled"}), 400
    note = str(payload.get("note") or "").strip()
    if len(note) > 300:
        return jsonify({"error": "note must be 300 characters or fewer"}), 400

    connection = get_connection()
    cursor = connection.execute(
        """
        UPDATE saved_flights
        SET status = ?, note = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND username = ?
        """,
        (status, note, saved_flight_id, username),
    )
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Saved flight not found"}), 404
    return jsonify(get_saved_flight_record(saved_flight_id, username))


@app.delete("/saved-flights/<int:saved_flight_id>")
def delete_saved_flight(saved_flight_id):
    username, error = validate_username(request.args.get("username"))
    if error:
        return jsonify({"error": error}), 400

    connection = get_connection()
    cursor = connection.execute(
        "DELETE FROM saved_flights WHERE id = ? AND username = ?",
        (saved_flight_id, username),
    )
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Saved flight not found"}), 404
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
