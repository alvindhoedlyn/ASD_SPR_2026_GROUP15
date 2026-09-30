from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import json
import os
import requests
import random

load_dotenv()

DATABASE_NAME = "plan.db"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "..", "prompts", "plan_suggestions.txt")
DB_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://student-AlvindhoEdlyn-database:6001")
SHARED_API_URL = os.getenv("SHARED_API_URL", "http://shared-backend:5000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

if not OLLAMA_BASE_URL.endswith("/v1"):
    OLLAMA_BASE_URL += "/v1"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

WEATHER_POOL = [
    "Sunny", "Clear", "Partly Cloudy", "Overcast", "Light Rain",
    "Thunderstorms", "Breezy", "Windy", "Foggy", "Tropical Downpour"
]

ACTIVITY_CATEGORIES = {
    "Sightseeing": ["City tour", "Old town walk", "Harbor cruise", "Viewpoint photography"],
    "Adventure": ["Hiking trail", "Kayaking", "Snorkeling", "Rock climbing", "Bike rental"],
    "Culture": ["Museum visit", "Art gallery tour", "Historic site walk", "Local theater"],
    "Relaxation": ["Beach day", "Botanical gardens walk", "Spa visit", "Park picnic"],
    "Food & Drink": ["Local market tasting", "Cafe hopping", "Street food tour", "Cooking class"],
    "Shopping": ["Boutique shopping", "Souvenir hunting", "Craft market visit"]
}

WEATHER_RULES = {
    "Sunny": "Prefer an outdoor activity, since the weather is good for it.",
    "Clear": "Prefer an outdoor activity, since the weather is good for it.",
    "Partly Cloudy": "An outdoor activity is fine.",
    "Overcast": "An outdoor or indoor activity is both fine.",
    "Light Rain": "Lean toward an indoor or covered activity if possible.",
    "Thunderstorms": "Choose an indoor activity, since it isn't safe to be outside.",
    "Breezy": "An outdoor activity is fine.",
    "Windy": "Avoid activities like kayaking or cycling that are hard in strong wind.",
    "Foggy": "Avoid activities that rely on long-distance views, like viewpoint photography.",
    "Tropical Downpour": "Choose an indoor activity, since it isn't safe to be outside.",
}
DEFAULT_WEATHER_RULE = "Choose an activity that suits the weather described above."

MCP_TOOLS = [
    {
        "name": "available_journeys",
        "description": "List all available journeys (id, label, locations).",
        "endpoint": "/mcp/available-journeys",
        "inputs": [],
    },
    {
        "name": "generate_trip_itinerary",
        "description": "Generate and save an AI-written day-by-day trip itinerary for the logged-in user.",
        "endpoint": "/mcp/generate-trip-itinerary",
        "inputs": [
            {"name": "journey_id", "type": "number", "required": True},
            {"name": "duration", "type": "number", "required": True},
            {"name": "preferences", "type": "text", "required": False, "default": "General exploration"},
        ],
    },
]

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path=""
)

CORS(app, resources={r"/*": {"origins": "*"}})

client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

def load_prompt(filename):
    # Navigate up one level from 'backend' to '/app', then into 'prompts'
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_dir, "..", "prompts", filename)

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def mcp_mode_is_enabled(req):
    if not MCP_ENABLED:
        return False
    return req.headers.get("X-MCP-Mode", "on").strip().lower() in ("1", "true", "yes", "on")


def mcp_disabled_response():
    return jsonify({"error": "MCP mode is disabled"}), 403


# ===================== SESSION / OWNERSHIP HELPERS =====================

def get_current_user_id():
    """
    Resolves the caller's session token into a verified user_id by asking
    shared-api. Never trusts a client-supplied user_id/userId field -
    that value is attacker-controlled and was the original vulnerability.

    Looks for the token in an "Authorization: Bearer <token>" header first
    (used by script.js and mcp_script.js), falling back to a "?token="
    query param for any link-based navigation that still uses one.

    Returns (user_id, None) on success, or (None, (response, status)) on
    failure - callers should `return err` immediately when err is not None.
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not token:
        token = request.args.get("token")

    if not token:
        return None, (jsonify({"error": "Authentication required"}), 401)

    try:
        resp = requests.get(f"{SHARED_API_URL}/api/verify-session", params={"token": token}, timeout=5)
    except requests.exceptions.RequestException as e:
        return None, (jsonify({"error": f"Auth service unreachable: {str(e)}"}), 502)

    if resp.status_code != 200:
        return None, (jsonify({"error": "Invalid or expired session"}), 401)

    try:
        return resp.json()["user_id"], None
    except (ValueError, KeyError):
        return None, (jsonify({"error": "Auth service returned an invalid response"}), 502)


def get_trip_owner(trip_id):
    """
    Looks up which user owns a trip. Reuses the existing GET /api/trips
    list from the database service - its rows already include user_ID
    from `SELECT * FROM trip`, so no database-side change is needed.

    Returns the owning user_id, or None if the trip doesn't exist or the
    database service is unreachable/errors (callers should treat None as
    "not found" and respond 404, since a trip that can't be confirmed as
    the caller's should never be acted on).
    """
    try:
        resp = requests.get(f"{DB_SERVICE_URL}/api/trips", timeout=5)
    except requests.exceptions.RequestException:
        return None

    if resp.status_code != 200:
        return None

    for t in resp.json():
        if t["trip_ID"] == trip_id:
            return t["user_ID"]
    return None


def generate_ai_itinerary(duration, locations, preferences, daily_weathers):
    results = []

    # Attempt to load prompt template
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_dir, "..", "prompts", "weather_activity.txt")

    template = None
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        print(f"Warning: Prompt file not found at {prompt_path}. Using fallback generation.")

    for i in range(duration):
        weather = daily_weathers[i]
        location = locations[i % len(locations)]

        if template:
            prompt = template.format(
                weather=weather,
                location=location,
                preferences=preferences or "General exploration",
                categories=json.dumps(ACTIVITY_CATEGORIES, indent=2),
                weather_rule=WEATHER_RULES.get(weather, DEFAULT_WEATHER_RULE)
            )

            try:
                response = client.chat.completions.create(
                    model=OLLAMA_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a helpful travel planner. Output strictly valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5,
                    timeout=10
                )

                content = response.choices[0].message.content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1].replace("json", "").strip()

                ai_json = json.loads(content)
                act_item = ai_json.get("itinerary_item", f"Explore {location}")

                results.append({
                    "summary": f"{act_item}",
                    "activity": act_item,
                    "category": ai_json.get("category", "Sightseeing")
                })
                continue
            except Exception as e:
                print(f"Ollama generation failed for day {i+1}: {e}")

        # Fallback format: "Location: Selected Activity"
        fallback_cat = random.choice(list(ACTIVITY_CATEGORIES.keys()))
        fallback_item = random.choice(ACTIVITY_CATEGORIES[fallback_cat])

        results.append({
            "summary": f"{location}: {fallback_item}",
            "activity": fallback_item,
            "category": fallback_cat
        })

    return results

def create_trip(journey_id, duration, preferences, user_id):
    try:
        journey_id = int(journey_id)
        duration = int(duration)
    except (TypeError, ValueError):
        return jsonify({"error": "journeyId and duration must be integers"}), 400

    if journey_id < 1:
        return jsonify({"error": "journeyId must be at least 1"}), 400
    if duration < 1 or duration > 14:
        return jsonify({"error": "duration must be between 1 and 14 days"}), 400
    try:
        journey_resp = requests.get(f"{DB_SERVICE_URL}/api/journeys/{journey_id}", timeout=5)
        if journey_resp.status_code == 404:
            return jsonify({"error": "Journey not found"}), 404
        elif journey_resp.status_code != 200:
            return jsonify({"error": "Failed to retrieve journey data"}), 500

        journey = journey_resp.json()
        locations = journey["locations"]

        # Pick random weather per day and run AI generation
        daily_weathers = [random.choice(WEATHER_POOL) for _ in range(duration)]
        ai_generated_days = generate_ai_itinerary(duration, locations, preferences, daily_weathers)

        days_data = []
        for i in range(duration):
            location = locations[i % len(locations)]
            weather = daily_weathers[i]

            itinerary = ai_generated_days[i]["summary"]
            act_text = ai_generated_days[i]["activity"]
            category = ai_generated_days[i]["category"]

            days_data.append({
                "day_number": i + 1,
                "location": location,
                "weather": weather,
                "itinerary": itinerary,
                "activity": act_text,
                "category": category
            })

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

        # Format activity metadata for the frontend view
        formatted_days = []
        for d in created_trip["days"]:
            formatted_days.append({
                "day_number": d["day_number"],
                "summary": d["itinerary"],
                "location": d["location"],
                "activities": [
                    {"text": d["location"], "icon": "📍"},
                    {"text": f"Weather: {d['weather']}", "icon": "☀️"},
                    {"text": d["activity"], "icon": "📷"}
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

# ----- ROUTES -----

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    """Health endpoint used by the integrated Docker Compose CI check."""
    return {"status": "ok"}

@app.route("/ask-with-context", methods=["POST"])
def ask_with_context():
    if request.is_json:
        data = request.get_json() or {}
        question = str(data.get("question", "")).strip()
        itinerary_context = str(data.get("itinerary", "No itinerary provided."))
    else:
        question = request.form.get("question", "").strip()
        itinerary_context = request.form.get("itinerary", "No itinerary provided.")

    if not question:
        return "<p>Question is required.</p>", 400

    try:
        sys_imp = "You are a helpful travel assistant. Answer the user based on the itinerary provided."
        if os.path.exists(PROMPT_PATH):
            with open(PROMPT_PATH, "r", encoding="utf-8") as f:
                sys_imp = f.read()

        usr_resp = f"Itinerary Context:\n{itinerary_context}\n\nUser Question: {question}"

        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": sys_imp},
                {"role": "user", "content": usr_resp},
            ],
            max_tokens=300,
            temperature=0.5,
        )

        answer = response.choices[0].message.content
        return f"<p>{answer}</p>", 200

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
    user_id, err = get_current_user_id()
    if err:
        return err

    try:
        # Fetch raw trips data from database service
        response = requests.get(f"{DB_SERVICE_URL}/api/trips", timeout=5)
        if response.status_code != 200:
            return jsonify(response.json()), response.status_code

        # Only ever return trips owned by the caller - this is the fix for
        # the cross-user data leak (every user could previously see every
        # other user's trips here).
        db_trips = [t for t in response.json() if t["user_ID"] == user_id]
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
                        {"text": loc, "icon": "📍"},
                        {"text": f"Weather: {d['weather']}", "icon": "☀️"},
                        {"text": d['activity'], "icon": "📷"}
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
    user_id, err = get_current_user_id()
    if err:
        return err

    data = request.get_json() or {}
    return create_trip(
        data.get("journeyId"),
        data.get("duration"),
        data.get("preferences", ""),
        user_id,
    )

@app.route("/api/trips/<int:trip_id>/regenerate", methods=["PUT"])
def regenerate_trip(trip_id):
    user_id, err = get_current_user_id()
    if err:
        return err

    owner = get_trip_owner(trip_id)
    if owner is None:
        return jsonify({"error": "Trip not found"}), 404
    if owner != user_id:
        return jsonify({"error": "Forbidden"}), 403

    try:
        # 1. Fetch existing trip details
        detail_resp = requests.get(f"{DB_SERVICE_URL}/api/trips/{trip_id}/details", timeout=5)
        if detail_resp.status_code == 404:
            return jsonify({"error": "Trip not found"}), 404
        elif detail_resp.status_code != 200:
            return jsonify({"error": "Failed to retrieve trip details"}), 500

        trip_data = detail_resp.json()

        # Print debug log to inspect exact JSON payload received from database service
        print(f"DEBUG [regenerate_trip] Received trip_data: {trip_data}")

        # Extract existing days and locations
        existing_days = trip_data.get("days", [])
        locations = trip_data.get("locations", ["Location"])

        # Determine exact duration (Priority: direct key -> days array count -> locations fallback)
        raw_duration = trip_data.get("duration") or trip_data.get("duration")
        if raw_duration is not None and int(raw_duration) > 0:
            duration = int(raw_duration)
        elif len(existing_days) > 0:
            duration = len(existing_days)
        else:
            # Fallback: Query direct days route if details payload lacked days
            days_resp = requests.get(f"{DB_SERVICE_URL}/api/trips/{trip_id}/days", timeout=5)
            if days_resp.status_code == 200 and len(days_resp.json()) > 0:
                duration = len(days_resp.json())
            else:
                duration = 1

        journey_id = trip_data.get("journey_id")
        label = trip_data.get("label", "Trip")

        print(f"DEBUG [regenerate_trip] Resolved duration to: {duration}")

        # 2. Pick new random weather conditions for each day
        daily_weathers = [random.choice(WEATHER_POOL) for _ in range(duration)]

        # 3. Generate brand-new AI itineraries
        ai_generated_days = generate_ai_itinerary(
            duration=duration,
            locations=locations,
            preferences="General exploration",
            daily_weathers=daily_weathers
        )

        # 4. Construct updated days payload
        updated_days = []
        formatted_days = []

        for i in range(duration):
            location = locations[i % len(locations)]
            weather = daily_weathers[i]
            itinerary = ai_generated_days[i]["summary"]
            act_text = ai_generated_days[i]["activity"]
            category = ai_generated_days[i]["category"]
            day_num = i + 1

            updated_days.append({
                "day_number": day_num,
                "location": location,
                "weather": weather,
                "itinerary": itinerary,
                "activity": act_text,
                "category": category
            })

            formatted_days.append({
                "day_number": day_num,
                "summary": itinerary,
                "location": location,
                "activities": [
                    {"text": location, "icon": "📍"},
                    {"text": f"Weather: {weather}", "icon": "☀️"},
                    {"text": act_text, "icon": "📷"}
                ]
            })

        # 5. Overwrite existing trip days in DB service
        update_payload = {"days": updated_days}
        update_resp = requests.put(
            f"{DB_SERVICE_URL}/api/trips/{trip_id}",
            json=update_payload,
            timeout=5
        )

        if update_resp.status_code != 200:
            return jsonify(update_resp.json()), update_resp.status_code

        # 6. Return full regenerated trip response
        return jsonify({
            "trip_id": trip_id,
            "user_id": user_id,
            "journey_id": journey_id,
            "duration": duration,
            "label": label,
            "days": formatted_days
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["PUT"])
def regenerate_day(trip_id, day_number):
    user_id, err = get_current_user_id()
    if err:
        return err

    owner = get_trip_owner(trip_id)
    if owner is None:
        return jsonify({"error": "Trip not found"}), 404
    if owner != user_id:
        return jsonify({"error": "Forbidden"}), 403

    try:
        # 1. Fetch trip details to determine location
        detail_resp = requests.get(f"{DB_SERVICE_URL}/api/trips/{trip_id}/details", timeout=5)
        if detail_resp.status_code == 404:
            return jsonify({"error": "Trip not found"}), 404
        elif detail_resp.status_code != 200:
            return jsonify({"error": "Failed to retrieve trip details"}), 500

        locations = detail_resp.json().get("locations", ["Location"])
        location = locations[(day_number - 1) % len(locations)]

        # 2. Pick a new random weather condition
        new_weather = random.choice(WEATHER_POOL)

        # 3. Request dynamic AI generation for 1 day
        ai_res = generate_ai_itinerary(
            duration=1,
            locations=[location],
            preferences="General exploration",
            daily_weathers=[new_weather]
        )

        if not ai_res:
            return jsonify({"error": "Failed to generate itinerary"}), 500

        day_data = ai_res[0]
        new_itinerary = day_data.get("summary", "")
        new_activity = day_data.get("activity", "")

        # 4. Send update payload matching database schema (without category)
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

        # 5. Format updated response for frontend UI
        return jsonify({
            "day_number": day_number,
            "summary": new_itinerary,
            "location": location,
            "activities": [
                {"text": location, "icon": "📍"},
                {"text": f"Weather: {new_weather}", "icon": "☀️"},
                {"text": new_activity, "icon": "📷"}
            ]
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["DELETE"])
def delete_day(trip_id, day_number):
    user_id, err = get_current_user_id()
    if err:
        return err

    owner = get_trip_owner(trip_id)
    if owner is None:
        return jsonify({"error": "Trip not found"}), 404
    if owner != user_id:
        return jsonify({"error": "Forbidden"}), 403

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
    user_id, err = get_current_user_id()
    if err:
        return err

    owner = get_trip_owner(trip_id)
    if owner is None:
        return jsonify({"error": "Trip not found"}), 404
    if owner != user_id:
        return jsonify({"error": "Forbidden"}), 403

    try:
        # Proxy DELETE request directly to database microservice
        resp = requests.delete(f"{DB_SERVICE_URL}/api/trips/{trip_id}", timeout=5)
        return jsonify(resp.json()), resp.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/mcp/tools", methods=["GET"])
def mcp_list_tools():
    if not mcp_mode_is_enabled(request):
        return mcp_disabled_response()
    return jsonify({"tools": MCP_TOOLS})

@app.route("/mcp/available-journeys", methods=["POST"])
def mcp_available_journeys():
    if not mcp_mode_is_enabled(request):
        return mcp_disabled_response()
    try:
        resp = requests.get(f"{DB_SERVICE_URL}/api/journeys", timeout=5)
        return jsonify({"tool": "available_journeys", "input": {}, "result": resp.json()}), resp.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Database service unreachable: {str(e)}"}), 502

@app.route("/mcp/generate-trip-itinerary", methods=["POST"])
def mcp_generate_trip_itinerary():
    if not mcp_mode_is_enabled(request):
        return mcp_disabled_response()

    user_id, err = get_current_user_id()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    try:
        journey_id = int(data.get("journey_id"))
        duration = int(data.get("duration"))
    except (TypeError, ValueError):
        return jsonify({"error": "journey_id and duration must be numbers"}), 400

    preferences = data.get("preferences") or "General exploration"
    resp, status = create_trip(journey_id, duration, preferences, user_id)
    return jsonify({
        "tool": "generate_trip_itinerary",
        "input": {"journey_id": journey_id, "duration": duration,
                  "preferences": preferences},
        "result": resp.get_json(),
    }), status

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)