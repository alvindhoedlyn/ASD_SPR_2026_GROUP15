import os
import sqlite3
from pathlib import Path
from flask import Flask, jsonify, request
from init_db import initialise_database

BASE_DIR = Path(__file__).resolve().parent

DATABASE_NAME = os.getenv(
    "DATABASE_PATH",
    str(BASE_DIR / "data" / "location_recommender.db")
)

app = Flask(__name__)

initialise_database()

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_missing_place_fields(data):
    required_fields = [
        "attraction_name",
        "city",
        "country",
        "category",
        "longitude",
        "latitude",
        "estimated_cost",
        "currency",
        "expected_duration_minutes",
        "indoor_outdoor",
        "crowd_level",
        "beginner_friendliness_score",
        "accessibility_information",
        "attraction_description"
    ]

    return [
        field for field in required_fields
        if field not in data or data[field] in (None, "")
    ]


def get_missing_recommendation_fields(data):
    required_fields = [
        "journey_id",
        "destination_city",
        "arrival_date",
        "departure_date",
        "interests",
        "weather_preferences",
        "crowd_tolerance",
        "budget_range",
        "accessibility_needs",
        "status"
    ]

    return [
        field for field in required_fields
        if field not in data or data[field] in (None, "")
    ]


@app.get("/")
@app.get("/health")
def health():
    return jsonify({
        "service": "location-recommender-database",
        "status": "running"
    }), 200


@app.get("/places")
def get_places():
    conn = get_db_connection()

    try:
        places = conn.execute(
            """
            SELECT *
            FROM places
            ORDER BY attraction_id
            """
        ).fetchall()

        return jsonify([
            dict(place) for place in places
        ]), 200

    finally:
        conn.close()


@app.get("/places/<int:attraction_id>")
def get_place(attraction_id):
    conn = get_db_connection()

    try:
        place = conn.execute(
            """
            SELECT *
            FROM places
            WHERE attraction_id = ?
            """,
            (attraction_id,)
        ).fetchone()

        if place is None:
            return jsonify({
                "error": "Place not found"
            }), 404

        return jsonify(dict(place)), 200

    finally:
        conn.close()


@app.post("/places")
def add_place():
    data = request.get_json(silent=True) or {}

    missing_fields = get_missing_place_fields(data)

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            INSERT INTO places (
                attraction_name,
                city,
                country,
                category,
                longitude,
                latitude,
                estimated_cost,
                currency,
                expected_duration_minutes,
                indoor_outdoor,
                crowd_level,
                beginner_friendliness_score,
                accessibility_information,
                attraction_description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["attraction_name"],
                data["city"],
                data["country"],
                data["category"],
                data["longitude"],
                data["latitude"],
                data["estimated_cost"],
                data["currency"],
                data["expected_duration_minutes"],
                data["indoor_outdoor"],
                data["crowd_level"],
                data["beginner_friendliness_score"],
                data["accessibility_information"],
                data["attraction_description"]
            )
        )

        conn.commit()

        return jsonify({
            "message": "Place added successfully",
            "attraction_id": cursor.lastrowid
        }), 201

    except sqlite3.IntegrityError as exc:
        conn.rollback()

        return jsonify({
            "error": "Invalid place data",
            "details": str(exc)
        }), 400

    finally:
        conn.close()


@app.put("/places/<int:attraction_id>")
def update_place(attraction_id):
    data = request.get_json(silent=True) or {}

    missing_fields = get_missing_place_fields(data)

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            UPDATE places
            SET attraction_name = ?,
                city = ?,
                country = ?,
                category = ?,
                longitude = ?,
                latitude = ?,
                estimated_cost = ?,
                currency = ?,
                expected_duration_minutes = ?,
                indoor_outdoor = ?,
                crowd_level = ?,
                beginner_friendliness_score = ?,
                accessibility_information = ?,
                attraction_description = ?
            WHERE attraction_id = ?
            """,
            (
                data["attraction_name"],
                data["city"],
                data["country"],
                data["category"],
                data["longitude"],
                data["latitude"],
                data["estimated_cost"],
                data["currency"],
                data["expected_duration_minutes"],
                data["indoor_outdoor"],
                data["crowd_level"],
                data["beginner_friendliness_score"],
                data["accessibility_information"],
                data["attraction_description"],
                attraction_id
            )
        )

        if cursor.rowcount == 0:
            return jsonify({
                "error": "Place not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Place updated successfully",
            "attraction_id": attraction_id
        }), 200

    except sqlite3.IntegrityError as exc:
        conn.rollback()

        return jsonify({
            "error": "Invalid place data",
            "details": str(exc)
        }), 400

    finally:
        conn.close()


@app.delete("/places/<int:attraction_id>")
def delete_place(attraction_id):
    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            DELETE FROM places
            WHERE attraction_id = ?
            """,
            (attraction_id,)
        )

        if cursor.rowcount == 0:
            return jsonify({
                "error": "Place not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Place deleted successfully",
            "attraction_id": attraction_id
        }), 200

    except sqlite3.IntegrityError as exc:
        conn.rollback()

        return jsonify({
            "error": "Place could not be deleted",
            "details": str(exc)
        }), 409

    finally:
        conn.close()

@app.get("/recommendation-requests")
def get_recommendation_requests():
    conn = get_db_connection()

    try:
        requests = conn.execute(
            """
            SELECT *
            FROM recommendation_requests
            ORDER BY request_id"""
        ).fetchall()

        return jsonify([
            dict(request) for request in requests
        ]), 200

    finally:
        conn.close()


@app.get("/recommendation-requests/<int:request_id>")
def get_recommendation_request(request_id):
    conn = get_db_connection()

    try:
        request_data = conn.execute(
            """
            SELECT *
            FROM recommendation_requests
            WHERE request_id = ?
            """, (request_id,)
        ).fetchone()

        if not request_data:
            return jsonify({
                "error": "Recommendation request not found"
            }), 404

        return jsonify(dict(request_data)), 200

    finally:
        conn.close()

@app.post("/recommendation-requests")
def add_recommendation_request():
    data = request.get_json(silent = True) or {}

    missing_fields = get_missing_recommendation_fields(data)

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
            }), 400
    
    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            INSERT INTO recommendation_requests (
            journey_id,
            destination_city,
            arrival_date, 
            departure_date,
            interests,
            weather_preferences,
            crowd_tolerance,
            budget_range,
            accessibility_needs,
            status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, 
            (data["journey_id"],
             data["destination_city"],
             data["arrival_date"],
             data["departure_date"],
             data["interests"],
             data["weather_preferences"],
             data["crowd_tolerance"],
             data["budget_range"],
             data["accessibility_needs"],
             data["status"]
             )
        )

        conn.commit()

        return jsonify({
            "message": "Recommendation request added successfully",
            "request_id": cursor.lastrowid
        }), 201

    except sqlite3.IntegrityError as exc:
        conn.rollback()

        return jsonify({
            "error": "Invalid recommendation request data",
            "details": str(exc)
        }), 400

    finally:
        conn.close()
        

@app.put("/recommendation-requests/<int:request_id>")
def update_recommendation_request(request_id):
    data = request.get_json(silent = True) or {}

    missing_fields = get_missing_recommendation_fields(data)

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            UPDATE recommendation_requests
            SET journey_id = ?,
                destination_city = ?,
                arrival_date = ?, 
                departure_date = ?,
                interests = ?,
                weather_preferences = ?,
                crowd_tolerance = ?,
                budget_range = ?,
                accessibility_needs = ?,
                status = ?
            WHERE request_id = ?
            """, (
                data["journey_id"],
                data["destination_city"],
                data["arrival_date"],
                data["departure_date"],
                data["interests"],
                data["weather_preferences"],
                data["crowd_tolerance"],
                data["budget_range"],
                data["accessibility_needs"],
                data["status"],
                request_id,
            )
        )

        if cursor.rowcount == 0:
            return jsonify({
                "error": "Recommendation request not found"
            }), 404
        
        conn.commit()

        return jsonify({
            "message": "Recommendation request updated successfully",
            "request_id": request_id
        }), 200
    except sqlite3.IntegrityError as exc:
        conn.rollback()

        return jsonify({
            "error": "Invalid recommendation request data",
            "details": str(exc)
        }), 400

    finally:
        conn.close()


@app.delete("/recommendation-requests/<int:request_id>")
def delete_recommendation_request(request_id):
    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            DELETE FROM recommendation_requests
            WHERE request_id = ?
            """, (request_id,)
        )

        if cursor.rowcount == 0:
            return jsonify({
                "error": "Recommendation request not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Recommendation request deleted successfully",
            "request_id": request_id
        }), 200

    except sqlite3.IntegrityError as exc:
        conn.rollback()

        return jsonify({
            "error": "Recommendation request could not be deleted",
            "details": str(exc)
        }), 409

    finally:
        conn.close()

    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)