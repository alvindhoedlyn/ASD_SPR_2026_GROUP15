from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import sqlite3
import json
import os

load_dotenv()

DATABASE_NAME = "plan.db"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path=""
)

CORS(app, resources={r"/*": {"origins": "*"}})

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"
)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def load_prompt(filename):
    path_inside_backend = Path(__file__).resolve().parent / "prompts" / filename
    if path_inside_backend.exists():
        return path_inside_backend.read_text(encoding="utf-8").strip()

    path_root = Path(__file__).resolve().parent.parent / "prompts" / filename
    if path_root.exists():
        return path_root.read_text(encoding="utf-8").strip()

    raise FileNotFoundError(f"Could not locate prompt file '{filename}'.")

# ----- ROUTES -----

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask-with-context", methods=["POST"])
def ask_with_context():
    if request.is_json:
        data = request.get_json() or {}
        question = str(data.get("question", "")).strip()
        itinerary_context = str(data.get("itinerary", "Take based on context if user"))
    else:
        question = request.form.get("question", "").strip()
        itinerary_context = request.form.get("itinerary", "No itinerary provided yet.")

    if not question:
        return "<p>Question is required.</p>", 400

    try:
        sys_imp = load_prompt("plan_suggestions.txt")
        usr_resp = f"Itinerary Context:\n{itinerary_context}\n\nUser Question: {question}"

        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": sys_imp},
                {"role": "user", "content": usr_resp},
            ],
            max_tokens=300,
            temperature=0,
        )

        answer = response.choices[0].message.content
        return f"<p>{answer}</p>"

    except Exception as exc:
        print(f"Backend Error: {exc}")
        return f"<p>Local AI agent request failed.</p><pre>{exc}</pre>", 500

@app.route("/api/journeys", methods=["GET"])
def get_journeys():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM journey")
        rows = cursor.fetchall()
        journeys = []
        for r in rows:
            journeys.append({
                "journey_id": r["journey_ID"],
                "label": r["label"],
                "locations": json.loads(r["locations"])
            })
        conn.close()
        return jsonify(journeys), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips", methods=["GET"])
def get_trips():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM trip ORDER BY trip_ID ASC")
        db_trips = cursor.fetchall()

        trips_list = []
        for t in db_trips:
            trip_id = t["trip_ID"]

            cursor.execute(
                """
                SELECT t.trip_ID, j.locations 
                FROM trip t
                JOIN journey j ON t.journey_ID = j.journey_ID
                WHERE t.trip_ID = ?
                """,
                (trip_id,),
            )
            journey_data = cursor.fetchone()
            locations = json.loads(journey_data["locations"]) if journey_data else ["Location"]

            cursor.execute(
                "SELECT * FROM day WHERE trip_ID = ? ORDER BY day_ID ASC",
                (trip_id,),
            )
            db_days = cursor.fetchall()

            days_list = []
            for idx, d in enumerate(db_days):
                loc = locations[idx % len(locations)]
                days_list.append({
                    "day_number": idx + 1,
                    "summary": d["itinerary"],
                    "location": loc,
                    "activities": [
                        {"text": d["activity"], "icon": "📍"},
                        {"text": f"Weather: {d['weather']}", "icon": "☀️"}
                    ]
                })

            trips_list.append({
                "trip_id": trip_id,
                "journey_id": t["journey_ID"],
                "duration": t["duration"],
                "days": days_list
            })

        conn.close()
        return jsonify(trips_list), 200

    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/generate", methods=["POST"])
def generate_trip():
    data = request.get_json() or {}
    journey_id = data.get("journeyId")
    duration = data.get("duration")
    preferences = data.get("preferences", "")
    user_id = data.get("userId", 1)

    if not journey_id or not duration or int(duration) < 1:
        return jsonify({"error": "Valid journeyId and duration required."}), 400

    duration = int(duration)
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM journey WHERE journey_ID = ?", (journey_id,))
        journey = cursor.fetchone()

        if not journey:
            conn.close()
            return jsonify({"error": "Journey not found"}), 404

        locations = json.loads(journey["locations"])

        cursor.execute(
            "INSERT INTO trip (user_ID, journey_ID, duration) VALUES (?, ?, ?)",
            (user_id, journey_id, duration),
        )
        new_trip_id = cursor.lastrowid

        created_days = []
        for i in range(duration):
            location = locations[i % len(locations)]
            weather = "Sunny"
            itinerary = f"{location} Visit"
            act_text = f"Exploring {location} (Pref: {preferences or 'General'})"

            cursor.execute(
                """
                INSERT INTO day (trip_ID, weather, itinerary, activity)
                VALUES (?, ?, ?, ?)
                """,
                (new_trip_id, weather, itinerary, act_text),
            )

            created_days.append({
                "day_number": i + 1,
                "summary": itinerary,
                "location": location,
                "activities": [
                    {"text": act_text, "icon": "📍"},
                    {"text": f"Weather: {weather}", "icon": "☀️"},
                    {"text": "Local Exploration", "icon": "📷"}
                ]
            })

        conn.commit()
        conn.close()

        return jsonify({
            "trip_id": new_trip_id,
            "user_id": user_id,
            "journey_id": journey_id,
            "duration": duration,
            "label": journey["label"],
            "days": created_days,
        }), 201

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["PUT"])
def regenerate_day(trip_id, day_number):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT t.trip_ID, j.locations 
            FROM trip t
            JOIN journey j ON t.journey_ID = j.journey_ID
            WHERE t.trip_ID = ?
            """,
            (trip_id,),
        )
        trip_data = cursor.fetchone()

        if not trip_data:
            conn.close()
            return jsonify({"error": "Trip not found"}), 404

        cursor.execute(
            """
            SELECT day_ID FROM day 
            WHERE trip_ID = ? 
            ORDER BY day_ID ASC 
            LIMIT 1 OFFSET ?
            """,
            (trip_id, day_number - 1),
        )
        target_day = cursor.fetchone()

        if not target_day:
            conn.close()
            return jsonify({"error": "Day not found"}), 404

        locations = json.loads(trip_data["locations"])
        location = locations[(day_number - 1) % len(locations)]

        new_weather = "Clear"
        new_itinerary = f"{location} Guided Tour"
        new_activity = f"Exploration & Activities around {location}"

        cursor.execute(
            """
            UPDATE day 
            SET weather = ?, itinerary = ?, activity = ?
            WHERE day_ID = ?
            """,
            (new_weather, new_itinerary, new_activity, target_day["day_ID"]),
        )

        conn.commit()
        conn.close()

        return jsonify({
            "day_number": day_number,
            "summary": new_itinerary,
            "location": location,
            "activities": [
                {"text": new_activity, "icon": "📍"},
                {"text": f"Weather: {new_weather}", "icon": "☀️"},
                {"text": "Local Sightseeing", "icon": "📷"}
            ]
        }), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>/regenerate", methods=["PUT"])
def regenerate_trip(trip_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT t.trip_ID, t.duration, j.locations 
            FROM trip t
            JOIN journey j ON t.journey_ID = j.journey_ID
            WHERE t.trip_ID = ?
            """,
            (trip_id,),
        )
        trip_data = cursor.fetchone()

        if not trip_data:
            conn.close()
            return jsonify({"error": "Trip not found"}), 404

        duration = trip_data["duration"]
        locations = json.loads(trip_data["locations"])

        cursor.execute("DELETE FROM day WHERE trip_ID = ?", (trip_id,))

        new_days = []
        for i in range(duration):
            day_num = i + 1
            location = locations[i % len(locations)]
            weather = "Sunny"
            itinerary = f"{location} Highlights"
            activity = f"Fresh exploration of {location}"

            cursor.execute(
                """
                INSERT INTO day (trip_ID, weather, itinerary, activity)
                VALUES (?, ?, ?, ?)
                """,
                (trip_id, weather, itinerary, activity),
            )

            new_days.append({
                "day_number": day_num,
                "summary": itinerary,
                "location": location,
                "activities": [
                    {"text": activity, "icon": "📍"},
                    {"text": f"Weather: {weather}", "icon": "☀️"},
                    {"text": "Local Exploration", "icon": "📷"},
                ],
            })

        conn.commit()
        conn.close()

        return jsonify({"days": new_days}), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["DELETE"])
def delete_day(trip_id, day_number):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT day_ID FROM day 
            WHERE trip_ID = ? 
            ORDER BY day_ID ASC 
            LIMIT 1 OFFSET ?
            """,
            (trip_id, day_number - 1),
        )
        target_day = cursor.fetchone()

        if not target_day:
            conn.close()
            return jsonify({"error": "Day not found"}), 404

        cursor.execute("DELETE FROM day WHERE day_ID = ?", (target_day["day_ID"],))
        cursor.execute("UPDATE trip SET duration = duration - 1 WHERE trip_ID = ?", (trip_id,))

        conn.commit()
        conn.close()
        return jsonify({"message": "Day deleted successfully"}), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>", methods=["DELETE"])
def delete_trip(trip_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM day WHERE trip_ID = ?", (trip_id,))
        cursor.execute("DELETE FROM trip WHERE trip_ID = ?", (trip_id,))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"error": "Trip not found"}), 404

        conn.commit()
        conn.close()
        return jsonify({"message": "Trip deleted successfully"}), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)