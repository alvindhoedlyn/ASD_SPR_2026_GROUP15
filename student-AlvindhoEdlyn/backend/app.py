from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import json
import os
import requests
import random
import re
from urllib.parse import quote

load_dotenv()

DATABASE_NAME = "plan.db"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "..", "prompts", "plan_suggestions.txt")
DB_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://student-AlvindhoEdlyn-database:6001")
SHARED_API_URL = os.getenv("SHARED_API_URL", "http://shared-backend:5000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")

MCP_ENABLED = os.getenv("MCP_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://host.docker.internal:5100").rstrip("/")
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

# Shared multi-agent server (planner -> worker -> reviewer -> human). It runs on the host,
# like Ollama and the RAG service, so containers reach it through host.docker.internal.
MULTI_AGENT_URL = os.getenv("MULTI_AGENT_URL", "http://host.docker.internal:5300").rstrip("/")
MULTI_AGENT_ENABLED = os.getenv("MULTI_AGENT_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
# Three local-model steps can take minutes (the reviewer alone may wait 300 s on the server),
# so this must stay above the server's worst case of roughly 540 s.
MULTI_AGENT_TIMEOUT_SECONDS = float(os.getenv("MULTI_AGENT_TIMEOUT_SECONDS", "600"))
# Identifies this student's backend in the shared server's history and audit logs.
MULTI_AGENT_SERVICE_ID = os.getenv("MULTI_AGENT_SERVICE_ID", "student-AlvindhoEdlyn")
MULTI_AGENT_MAX_QUESTION_CHARS = 1000   # the shared server rejects anything longer
MULTI_AGENT_MAX_LOCATIONS = 10          # the shared server reads at most 10 evidence items
MULTI_AGENT_DECISIONS = ("accept", "partial", "correct", "reject")

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

def rag_mode_is_enabled(req):
    """Mirrors mcp_mode_is_enabled: env switch plus the X-RAG-Mode header sent by rag_script.js."""
    if not RAG_ENABLED:
        return False
    return req.headers.get("X-RAG-Mode", "on").strip().lower() in ("1", "true", "yes", "on")
 
 
def rag_request_guard():
    """
    Shared gate for every /rag/* route: RAG mode must be on and the caller must
    have a valid session. Returns (user_id, None) on success, or (None, error)
    in the same shape as get_current_user_id() - callers `return err` when set.
    """
    if not rag_mode_is_enabled(request):
        return None, (jsonify({"status": "error", "error": "RAG mode is disabled"}), 403)
    return get_current_user_id()
 
 
def forward_to_rag(path, payload, timeout):
    """POST payload to the local RAG service and relay its JSON body + status code unchanged."""
    try:
        resp = requests.post(f"{RAG_SERVICE_URL}{path}", json=payload, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "error": f"RAG service unreachable: {str(e)}"}), 502
 
    try:
        body = resp.json()
    except ValueError:
        return jsonify({"status": "error", "error": "RAG service returned an invalid response"}), 502
    return jsonify(body), resp.status_code
 
 
def parse_k(raw, default, maximum):
    """Client-supplied k, clamped to 1..maximum. Returns None if it isn't a number."""
    if raw is None:
        return default
    try:
        return max(1, min(int(raw), maximum))
    except (TypeError, ValueError):
        return None


# ===================== MULTI-AGENT HELPERS =====================

# Weather suitability. These turn the sentences in WEATHER_RULES into hard filters, so the
# shared worker is only ever offered activities that fit each location's weather.
WET_WEATHER = {"Light Rain", "Thunderstorms", "Tropical Downpour"}

OUTDOOR_ACTIVITIES = {
    "Old town walk", "Harbor cruise", "Viewpoint photography",
    "Hiking trail", "Kayaking", "Snorkeling", "Rock climbing", "Bike rental",
    "Historic site walk", "Beach day", "Botanical gardens walk", "Park picnic",
    "Street food tour",
}

WEATHER_EXCLUSIONS = {
    "Windy": {"Harbor cruise", "Kayaking", "Snorkeling", "Rock climbing", "Bike rental", "Park picnic", "Beach day"},
    "Foggy": {"Viewpoint photography"},
}

_WEATHER_LOOKUP = {w.lower(): w for w in WEATHER_POOL}

# Weather as people actually type it ("if it rains"), mapped onto WEATHER_POOL values. Longer
# phrases come first so "tropical downpour" wins over "downpour". Bare "clear" is only read as
# weather in phrases like "clear skies", because it is an ordinary English word; send
# {"weather": "Clear"} in the request body to set it explicitly.
_WEATHER_PHRASES = [
    (r"tropical downpours?|downpours?", "Tropical Downpour"),
    (r"thunderstorms?|thunder|stormy|storms?", "Thunderstorms"),
    (r"light rain|rain(?:s|y|ing)?|showers?|drizzl\w*", "Light Rain"),
    (r"partly cloudy|cloudy", "Partly Cloudy"),
    (r"overcast", "Overcast"),
    (r"foggy|fog|misty|mist", "Foggy"),
    (r"windy|wind", "Windy"),
    (r"breezy|breeze", "Breezy"),
    (r"sunny|sunshine|sun", "Sunny"),
    (r"clear (?:sky|skies|weather|day)s?", "Clear"),
]
_WEATHER_PATTERN = re.compile(
    r"\b(?:" + "|".join(f"(?P<w{i}>{phrase})" for i, (phrase, _) in enumerate(_WEATHER_PHRASES)) + r")\b",
    re.IGNORECASE,
)

# Words too common to identify a journey or location on their own ("beach", "ocean", "weekend").
GENERIC_WORDS = {
    "beach", "national", "market", "markets", "valley", "mountains", "bridge", "island",
    "harbour", "harbor", "central", "museum", "canyon", "rainforest", "vineyards", "great",
    "weekend", "adventure", "explorer", "culture", "north", "wilderness", "centre",
    "tropical", "ocean", "foodie", "foodies", "twelve", "springs", "house", "gorge", "kings",
}


def multi_agent_mode_is_enabled(req):
    """Mirrors rag_mode_is_enabled: env switch plus an X-Multi-Agent-Mode header from the frontend."""
    if not MULTI_AGENT_ENABLED:
        return False
    return req.headers.get("X-Multi-Agent-Mode", "on").strip().lower() in ("1", "true", "yes", "on")


def multi_agent_request_guard():
    """Gate for every /multi-agent/* route: mode must be on and the caller must have a valid
    session. Same (user_id, err) shape as get_current_user_id()."""
    if not multi_agent_mode_is_enabled(request):
        return None, (jsonify({"status": "error", "error": "Multi-agent mode is disabled"}), 403)
    return get_current_user_id()


def multi_agent_caller(user_id):
    """Set server-side from the verified session, never from the browser. The shared server
    keeps only 40 characters, so truncate here too and compare like with like."""
    return f"{MULTI_AGENT_SERVICE_ID}:user-{user_id}"[:40]


def call_multi_agent(method, path, payload=None, timeout=15):
    """Call the shared server. Returns (body, status, None) or (None, None, (response, status))."""
    try:
        resp = requests.request(method, f"{MULTI_AGENT_URL}{path}", json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        return None, None, (jsonify({"status": "error", "error": "Multi-agent service timed out"}), 504)
    except requests.exceptions.RequestException as e:
        return None, None, (jsonify({"status": "error", "error": f"Multi-agent service unreachable: {str(e)}"}), 502)

    try:
        return resp.json(), resp.status_code, None
    except ValueError:
        return None, None, (jsonify({"status": "error", "error": "Multi-agent service returned an invalid response"}), 502)


def fetch_owned_workflow(workflow_id, user_id):
    """Fetch a workflow and confirm it belongs to this user. The shared server serves any
    workflow id to any caller, so ownership is enforced here using the `caller` it recorded.
    Someone else's workflow gets the same 404 as a missing one, so ids can't be probed."""
    body, status, err = call_multi_agent("GET", f"/workflow/{quote(workflow_id, safe='')}")
    if err:
        return None, err
    if status != 200:
        return None, (jsonify(body), status)
    if body.get("caller") != multi_agent_caller(user_id):
        return None, (jsonify({"status": "error", "error": "workflow not found"}), 404)
    return body, None


def normalise_weather(value):
    """Canonical WEATHER_POOL spelling, or None if it isn't a known condition."""
    return _WEATHER_LOOKUP.get(str(value or "").strip().lower())


def parse_supplied_weather(raw, names):
    """Weather sent by the frontend: one value for every location, or {location: value}.
    Returns ({location: weather}, None) or (None, error message)."""
    if raw in (None, "", {}):
        return {}, None

    allowed = ", ".join(WEATHER_POOL)
    if isinstance(raw, str):
        weather = normalise_weather(raw)
        if not weather:
            return None, f"weather must be one of: {allowed}"
        return {name: weather for name in names}, None

    if isinstance(raw, dict):
        by_lower = {name.lower(): name for name in names}
        result = {}
        for key, value in raw.items():
            weather = normalise_weather(value)
            if not weather:
                return None, f"weather for '{key}' must be one of: {allowed}"
            name = by_lower.get(str(key).strip().lower())
            if name:
                result[name] = weather
        return result, None

    return None, "weather must be a string or an object keyed by location"


def find_weather(text):
    """(position, canonical weather) for every weather word or phrase in the text."""
    return [
        (match.start(), _WEATHER_PHRASES[int(match.lastgroup[1:])][1])
        for match in _WEATHER_PATTERN.finditer(text)
    ]


def extract_question_weather(question, names):
    """Read weather out of the free-text question. A weather term is given to the nearest
    location named in the same sentence; if the whole question mentions exactly one weather
    type, it applies to every location that did not get its own."""
    result = {}

    for segment in re.split(r"[.;\n]+", question):
        lowered = segment.lower()
        positions = [(lowered.find(name.lower()), name) for name in names if name.lower() in lowered]
        if not positions:
            continue
        for position, weather in find_weather(segment):
            nearest = min(positions, key=lambda item: abs(item[0] - position))
            result.setdefault(nearest[1], weather)

    distinct = {weather for _, weather in find_weather(question)}
    if len(distinct) == 1:
        only = next(iter(distinct))
        for name in names:
            result.setdefault(name, only)

    return result


def suitable_activities(weather):
    """Every catalogue activity that suits the weather (all of them if the weather is unknown)."""
    activities = [a for acts in ACTIVITY_CATEGORIES.values() for a in acts]
    if not weather:
        return activities
    return [
        a for a in activities
        if not (weather in WET_WEATHER and a in OUTDOOR_ACTIVITIES)
        and a not in WEATHER_EXCLUSIONS.get(weather, set())
    ]


def distinctive_words(name):
    """Words of a journey label or location that can identify it ("Melbourne", "Uluru")."""
    return [w for w in re.findall(r"[a-z]+", name.lower()) if len(w) >= 5 and w not in GENERIC_WORDS]


def mentions_word(word, prompt_words):
    """True if the prompt uses the word, a plural or possessive of it, or a stem of it that is
    at most two letters shorter ("tasmania" for "tasmanian"). Anything looser would let
    "queensland" match "queen"."""
    return any(
        (w.startswith(word) and len(w) - len(word) <= 2)
        or (len(w) >= 5 and word.startswith(w) and len(word) - len(w) <= 2)
        for w in prompt_words
    )


def select_itinerary_locations(question, journeys, journey_id=None):
    """Locations the question is about, inferred from the free text.

    1. An explicit journey_id, or a journey label / location name written out in full.
    2. Otherwise, a distinctive word: "Melbourne" selects the whole Melbourne journey, while
       "Bondi" selects only Bondi Beach.
    A journey label selects every one of its locations; a location selects just itself."""
    lowered = question.lower()
    prompt_words = set(re.findall(r"[a-z]+", lowered))
    selected = []

    def add(journey, locations):
        for loc in locations:
            selected.append({"journey_id": journey.get("journey_id"),
                             "journey": str(journey.get("label") or ""), "location": loc})

    for journey in journeys:
        label = str(journey.get("label") or "")
        locations = [str(loc) for loc in journey.get("locations", [])]

        if journey_id is not None:
            add(journey, locations if journey.get("journey_id") == journey_id else [])
        elif label and label.lower() in lowered:
            add(journey, locations)
        else:
            add(journey, [loc for loc in locations if loc.lower() in lowered])

    if not selected and journey_id is None:
        for journey in journeys:
            label = str(journey.get("label") or "")
            locations = [str(loc) for loc in journey.get("locations", [])]

            if any(mentions_word(w, prompt_words) for w in distinctive_words(label)):
                add(journey, locations)
            else:
                add(journey, [loc for loc in locations
                              if any(mentions_word(w, prompt_words) for w in distinctive_words(loc))])

    return selected[:MULTI_AGENT_MAX_LOCATIONS]


def build_itinerary_evidence(selected, weather_by_location):
    """One record per location. A `name` field is what the shared reviewer uses to tell
    whether the worker covered a record, so every record needs one."""
    return [
        {
            "name": item["location"],
            "journey": item["journey"],
            "weather": weather_by_location.get(item["location"]) or "unknown",
            "allowed_activities": suitable_activities(weather_by_location.get(item["location"])),
        }
        for item in selected
    ]


# ----- ROUTES -----

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    """Health endpoint used by the integrated Docker Compose CI check."""
    return {"status": "ok", "student": "1"}

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
    
# MCP Mirror Routes
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

# RAG Mirror Routes
@app.route("/rag/refresh", methods=["POST"])
def rag_refresh():
    user_id, err = rag_request_guard()
    if err:
        return err
 
    # caller is set server-side from the verified session: the audit log should
    # not trust a browser-supplied value (same reasoning as get_current_user_id).
    return forward_to_rag("/refresh", {"caller": f"user-{user_id}"}, timeout=45)
 
 
@app.route("/rag/retrieve", methods=["POST"])
def rag_retrieve():
    user_id, err = rag_request_guard()
    if err:
        return err
 
    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or "").strip()
    if not query:
        return jsonify({"status": "error", "error": "query is required"}), 400
 
    k = parse_k(data.get("k"), default=5, maximum=20)
    if k is None:
        return jsonify({"status": "error", "error": "k must be a number"}), 400
 
    return forward_to_rag("/itinerary/search", {"query": query, "k": k, "caller": f"user-{user_id}"}, timeout=30)
 
 
@app.route("/rag/activities", methods=["POST"])
def rag_activities():
    user_id, err = rag_request_guard()
    if err:
        return err
 
    data = request.get_json(silent=True) or {}
    location = str(data.get("location") or "").strip()
    if not location:
        return jsonify({"status": "error", "error": "location is required"}), 400
 
    k = parse_k(data.get("k"), default=4, maximum=10)
    if k is None:
        return jsonify({"status": "error", "error": "k must be a number"}), 400
 
    payload = {
        "location": location,
        "weather": str(data.get("weather") or "").strip(),
        "k": k,
        "caller": f"user-{user_id}",
    }
    return forward_to_rag("/activities", payload, timeout=30)

# Multi-Agent Mirror Routes
@app.route("/multi-agent/workflow", methods=["POST"])
def multi_agent_workflow():
    """Answer a free-text itinerary question with the shared planner -> worker -> reviewer.

    Body: {"question": "...", "journey_id": 1 (optional), "weather": "Light Rain" or
           {"Bondi Beach": "Sunny"} (optional)}
    The result is the shared server's workflow record, left pending until a human decides.
    """
    user_id, err = multi_agent_request_guard()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or "").strip()
    if not question:
        return jsonify({"status": "error", "error": "question is required"}), 400
    if len(question) > MULTI_AGENT_MAX_QUESTION_CHARS:
        return jsonify({"status": "error",
                        "error": f"question must be at most {MULTI_AGENT_MAX_QUESTION_CHARS} characters"}), 400

    journey_id = None
    if data.get("journey_id") not in (None, ""):
        try:
            journey_id = int(data["journey_id"])
        except (TypeError, ValueError):
            return jsonify({"status": "error", "error": "journey_id must be a number"}), 400

    # 1. Evidence comes from this student's own database service.
    try:
        journeys_resp = requests.get(f"{DB_SERVICE_URL}/api/journeys", timeout=5)
        if journeys_resp.status_code != 200:
            return jsonify({"status": "error", "error": "Failed to retrieve journeys"}), 502
        journeys = journeys_resp.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "error": f"Database service unreachable: {str(e)}"}), 502
    except ValueError:
        return jsonify({"status": "error", "error": "Database service returned an invalid response"}), 502

    if journey_id is not None and not any(j.get("journey_id") == journey_id for j in journeys):
        return jsonify({"status": "error", "error": "Journey not found"}), 404

    selected = select_itinerary_locations(question, journeys, journey_id)
    if not selected:
        return jsonify({
            "status": "insufficient_context",
            "error": "The question does not mention a known journey or location.",
            "available_journeys": [j.get("label") for j in journeys],
        }), 422

    # 2. Weather: values sent by the frontend win over weather mentioned in the question.
    names = [item["location"] for item in selected]
    supplied, weather_err = parse_supplied_weather(data.get("weather"), names)
    if weather_err:
        return jsonify({"status": "error", "error": weather_err}), 400
    weather_by_location = {**extract_question_weather(question, names), **supplied}

    # 3. Hand the evidence to the shared server. caller comes from the verified session.
    payload = {
        "user_request": question,
        "feature": "itinerary",
        "evidence": build_itinerary_evidence(selected, weather_by_location),
        "caller": multi_agent_caller(user_id),
    }
    body, status, err = call_multi_agent("POST", "/workflow", payload, timeout=MULTI_AGENT_TIMEOUT_SECONDS)
    if err:
        return err
    if status != 200:
        return jsonify(body), status

    # Tell the frontend which locations had no weather, so it can ask for it.
    body["locations_without_weather"] = [n for n in names if n not in weather_by_location]
    return jsonify(body), 200


@app.route("/multi-agent/workflow/<workflow_id>", methods=["GET"])
def multi_agent_get_workflow(workflow_id):
    user_id, err = multi_agent_request_guard()
    if err:
        return err

    record, err = fetch_owned_workflow(workflow_id, user_id)
    if err:
        return err
    return jsonify(record), 200


@app.route("/multi-agent/workflow/<workflow_id>/decision", methods=["POST"])
def multi_agent_decision(workflow_id):
    """Human review: accept | partial | correct | reject (correct needs corrected_output)."""
    user_id, err = multi_agent_request_guard()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision") or "").strip().lower()
    if decision not in MULTI_AGENT_DECISIONS:
        return jsonify({"status": "error",
                        "error": "decision must be one of: " + ", ".join(MULTI_AGENT_DECISIONS)}), 400

    _, err = fetch_owned_workflow(workflow_id, user_id)
    if err:
        return err

    payload = {
        "decision": decision,
        "note": str(data.get("note") or ""),
        "corrected_output": str(data.get("corrected_output") or ""),
    }
    body, status, err = call_multi_agent("POST", f"/workflow/{quote(workflow_id, safe='')}/decision", payload)
    if err:
        return err
    return jsonify(body), status

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)