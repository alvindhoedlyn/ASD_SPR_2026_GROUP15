from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import json
import os
import requests

load_dotenv()

DATABASE_NAME = "plan.db"

DB_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://student-AlvindhoEdlyn-database:6001")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ai-mode:11434/v1")
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
    try:
        # Proxy request directly to the database service
        response = requests.get(f"{DB_SERVICE_URL}/api/journeys", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502

@app.route("/api/trips", methods=["GET"])
def get_trips():
    try:
        # Fetch raw trips data from database service
        response = requests.get(f"{DB_SERVICE_URL}/api/trips", timeout=5)
        if response.status_code != 200:
            return jsonify(response.json()), response.status_code

        db_trips = response.json()
        trips_list = []

        for t in db_trips:
            trip_id = t["trip_ID"]

            # Fetch details for specific trip join
            trip_detail_resp = requests.get(
                f"{DB_SERVICE_URL}/api/trips/{trip_id}/details", 
                timeout=5
            )
            
            locations = ["Location"]
            if trip_detail_resp.status_code == 200:
                locations = trip_detail_resp.json().get("locations", locations)

            # Fetch days for specific trip
            days_resp = requests.get(
                f"{DB_SERVICE_URL}/api/trips/{trip_id}/days", 
                timeout=5
            )
            db_days = days_resp.json() if days_resp.status_code == 200 else []

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

        return jsonify(trips_list), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
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

    try:
        # Fetch journey details from DB service to get locations and label
        journey_resp = requests.get(f"{DB_SERVICE_URL}/api/journeys/{journey_id}", timeout=5)
        if journey_resp.status_code == 404:
            return jsonify({"error": "Journey not found"}), 404
        elif journey_resp.status_code != 200:
            return jsonify({"error": "Failed to retrieve journey data"}), 500

        journey = journey_resp.json()
        locations = journey["locations"]

        # Build day items
        days_data = []
        for i in range(duration):
            location = locations[i % len(locations)]
            weather = "Sunny"
            itinerary = f"{location} Visit"
            act_text = f"Exploring {location} (Pref: {preferences or 'General'})"

            days_data.append({
                "day_number": i + 1,
                "location": location,
                "weather": weather,
                "itinerary": itinerary,
                "activity": act_text
            })

        # Send creation payload to database service
        db_payload = {
            "user_id": user_id,
            "journey_id": journey_id,
            "duration": duration,
            "days": days_data
        }

        create_resp = requests.post(f"{DB_SERVICE_URL}/api/trips", json=db_payload, timeout=5)
        if create_resp.status_code != 201:
            return jsonify(create_resp.json()), create_resp.status_code

        created_trip = create_resp.json()

        # Format output structure expected by frontend
        formatted_days = []
        for d in created_trip["days"]:
            formatted_days.append({
                "day_number": d["day_number"],
                "summary": d["itinerary"],
                "location": d["location"],
                "activities": [
                    {"text": d["activity"], "icon": "📍"},
                    {"text": f"Weather: {d['weather']}", "icon": "☀️"},
                    {"text": "Local Exploration", "icon": "📷"}
                ]
            })

        return jsonify({
            "trip_id": created_trip["trip_id"],
            "user_id": user_id,
            "journey_id": journey_id,
            "duration": duration,
            "label": journey["label"],
            "days": formatted_days,
        }), 201

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
 @app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["PUT"])
def regenerate_day(trip_id, day_number):
    try:
        # 1. Fetch trip details to determine location sequence
        detail_resp = requests.get(f"{DB_SERVICE_URL}/api/trips/{trip_id}/details", timeout=5)
        if detail_resp.status_code == 404:
            return jsonify({"error": "Trip not found"}), 404
        elif detail_resp.status_code != 200:
            return jsonify({"error": "Failed to retrieve trip details"}), 500

        locations = detail_resp.json().get("locations", ["Location"])
        location = locations[(day_number - 1) % len(locations)]

        new_weather = "Clear"
        new_itinerary = f"{location} Guided Tour"
        new_activity = f"Exploration & Activities around {location}"

        # 2. Send update payload to the database microservice
        update_payload = {
            "day_number": day_number,
            "weather": new_weather,
            "itinerary": new_itinerary,
            "activity": new_activity
        }

        update_resp = requests.put(
            f"{DB_SERVICE_URL}/api/trips/{trip_id}/days/{day_number}",
            json=update_payload,
            timeout=5
        )

        if update_resp.status_code != 200:
            return jsonify(update_resp.json()), update_resp.status_code

        # 3. Format response for the frontend UI
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

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["DELETE"])
def delete_day(trip_id, day_number):
    try:
        # Proxy DELETE request directly to database service
        resp = requests.delete(
            f"{DB_SERVICE_URL}/api/trips/{trip_id}/days/{day_number}",
            timeout=5
        )
        return jsonify(resp.json()), resp.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/trips/<int:trip_id>", methods=["DELETE"])
def delete_trip(trip_id):
    try:
        # Proxy DELETE request directly to database microservice
        resp = requests.delete(f"{DB_SERVICE_URL}/api/trips/{trip_id}", timeout=5)
        return jsonify(resp.json()), resp.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)