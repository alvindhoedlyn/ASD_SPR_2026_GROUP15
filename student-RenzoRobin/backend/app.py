import os
import requests
from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get("PORT", 5003))
DATABASE_API_URL = os.environ.get("DATABASE_API_URL", "http://student-RenzoRobin-database:6003")

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://ai-mode:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")

client = OpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama")


# ===================== DATABASE API CLIENT =====================
# Thin wrapper around the database microservice. Any failure there
# is surfaced as a 502 rather than crashing this service.

def db_request(method, path, **kwargs):
    url = f"{DATABASE_API_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=10, **kwargs)
        resp.raise_for_status()
        return resp.json(), resp.status_code
    except requests.exceptions.RequestException as exc:
        return {"error": "database service unavailable", "detail": str(exc)}, 502


def db_get(path, params=None):
    return db_request("GET", path, params=params)


def db_post(path, json_body=None):
    return db_request("POST", path, json=json_body)


def db_put(path, json_body=None):
    return db_request("PUT", path, json=json_body)


def db_delete(path):
    return db_request("DELETE", path)


@app.route("/health")
def health():
    return {"status": "ok", "service": "backend-api"}


# ===================== AREAS (proxy) =====================

@app.route("/areas", methods=["GET"])
def list_areas():
    body, status = db_get("/areas")
    return jsonify(body), status


# ===================== ACCOMMODATIONS CRUD (proxy) =====================

@app.route("/accommodations", methods=["POST"])
def create_accommodation():
    body, status = db_post("/accommodations", request.get_json())
    return jsonify(body), status


@app.route("/accommodations", methods=["GET"])
def list_accommodations():
    body, status = db_get("/accommodations", params=request.args)
    return jsonify(body), status


@app.route("/accommodations/<int:accommodation_id>", methods=["GET"])
def get_accommodation(accommodation_id):
    body, status = db_get(f"/accommodations/{accommodation_id}")
    return jsonify(body), status


@app.route("/accommodations/<int:accommodation_id>", methods=["PUT"])
def update_accommodation(accommodation_id):
    body, status = db_put(f"/accommodations/{accommodation_id}", request.get_json())
    return jsonify(body), status


@app.route("/accommodations/<int:accommodation_id>", methods=["DELETE"])
def delete_accommodation(accommodation_id):
    body, status = db_delete(f"/accommodations/{accommodation_id}")
    return jsonify(body), status


# ===================== ROOM TYPES CRUD (proxy) =====================

@app.route("/accommodations/<int:accommodation_id>/rooms", methods=["POST"])
def create_room(accommodation_id):
    body, status = db_post(f"/accommodations/{accommodation_id}/rooms", request.get_json())
    return jsonify(body), status


@app.route("/accommodations/<int:accommodation_id>/rooms", methods=["GET"])
def list_rooms(accommodation_id):
    body, status = db_get(f"/accommodations/{accommodation_id}/rooms")
    return jsonify(body), status


@app.route("/rooms/<int:room_id>", methods=["GET"])
def get_room(room_id):
    body, status = db_get(f"/rooms/{room_id}")
    return jsonify(body), status


@app.route("/rooms/<int:room_id>", methods=["PUT"])
def update_room(room_id):
    body, status = db_put(f"/rooms/{room_id}", request.get_json())
    return jsonify(body), status


@app.route("/rooms/<int:room_id>", methods=["DELETE"])
def delete_room(room_id):
    body, status = db_delete(f"/rooms/{room_id}")
    return jsonify(body), status


# ===================== PRIORITIES CRUD (proxy) =====================

@app.route("/priorities", methods=["POST"])
def create_priority():
    body, status = db_post("/priorities", request.get_json())
    return jsonify(body), status


@app.route("/priorities/<int:user_id>", methods=["GET"])
def get_priority(user_id):
    body, status = db_get(f"/priorities/{user_id}")
    return jsonify(body), status


@app.route("/priorities/<int:user_id>", methods=["PUT"])
def update_priority(user_id):
    body, status = db_put(f"/priorities/{user_id}", request.get_json())
    return jsonify(body), status


@app.route("/priorities/<int:user_id>", methods=["DELETE"])
def delete_priority(user_id):
    body, status = db_delete(f"/priorities/{user_id}")
    return jsonify(body), status


# ===================== LISTS CRUD (proxy) =====================

@app.route("/lists", methods=["POST"])
def create_list():
    body, status = db_post("/lists", request.get_json())
    return jsonify(body), status


@app.route("/lists/<int:user_id>", methods=["GET"])
def get_user_lists(user_id):
    body, status = db_get(f"/lists/{user_id}")
    return jsonify(body), status


@app.route("/lists/<int:list_id>", methods=["PUT"])
def rename_list(list_id):
    body, status = db_put(f"/lists/{list_id}", request.get_json())
    return jsonify(body), status


@app.route("/lists/<int:list_id>", methods=["DELETE"])
def delete_list(list_id):
    body, status = db_delete(f"/lists/{list_id}")
    return jsonify(body), status


@app.route("/lists/<int:list_id>/accommodations", methods=["POST"])
def add_to_list(list_id):
    body, status = db_post(f"/lists/{list_id}/accommodations", request.get_json())
    return jsonify(body), status


@app.route("/lists/<int:list_id>/accommodations", methods=["GET"])
def get_list_accommodations(list_id):
    body, status = db_get(f"/lists/{list_id}/accommodations", params=request.args)
    return jsonify(body), status


@app.route("/list-accommodations/<int:list_accom_id>", methods=["PUT"])
def update_list_accommodation(list_accom_id):
    body, status = db_put(f"/list-accommodations/{list_accom_id}", request.get_json())
    return jsonify(body), status


@app.route("/list-accommodations/<int:list_accom_id>", methods=["DELETE"])
def remove_from_list(list_accom_id):
    body, status = db_delete(f"/list-accommodations/{list_accom_id}")
    return jsonify(body), status


# ===================== RECOMMENDATION SCORING (business logic lives here) =====================

def score_accommodation(accom, weights, all_accoms, desired_facilities, target_city):
    max_price = max((a["min_price"] for a in all_accoms), default=1) or 1
    price_score = 1 - (accom["min_price"] / max_price)

    location_score = 1.0 if target_city and target_city.lower() in accom["city_area"].lower() else 0.4

    if desired_facilities:
        facility_score = len(set(desired_facilities) & set(accom["facilities"])) / len(desired_facilities)
    else:
        facility_score = 0.5

    max_reviews = max((a["review_count"] for a in all_accoms), default=1) or 1
    review_score = (accom["avg_rating"] / 5) * 0.7 + (accom["review_count"] / max_reviews) * 0.3

    weight_sum = weights["price_weight"] + weights["location_weight"] + weights["facility_weight"] + weights["review_weight"]
    weight_sum = weight_sum or 1

    total = (
        price_score * weights["price_weight"] +
        location_score * weights["location_weight"] +
        facility_score * weights["facility_weight"] +
        review_score * weights["review_weight"]
    ) / weight_sum

    return total, {
        "price_score": round(price_score, 3),
        "location_score": round(location_score, 3),
        "facility_score": round(facility_score, 3),
        "review_score": round(review_score, 3),
    }


@app.route("/recommendations", methods=["POST"])
def generate_recommendations():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    target_city = data.get("city")
    desired_facilities = data.get("desired_facilities", [])

    weights, status = db_get(f"/priorities/{user_id}")
    if status >= 400:
        return jsonify(weights), status

    all_accoms, status = db_get("/internal/accommodations-with-price")
    if status >= 400:
        return jsonify(all_accoms), status

    if target_city:
        all_accoms = [a for a in all_accoms if a["city_area"] == target_city]

    scored = []
    for accom in all_accoms:
        total, breakdown = score_accommodation(accom, weights, all_accoms, desired_facilities, target_city)
        scored.append({
            "accommodation_id": accom["accommodation_id"],
            "name": accom["name"],
            "city_area": accom["city_area"],
            "avg_rating": accom["avg_rating"],
            "review_count": accom["review_count"],
            "starting_price": accom["min_price"],
            "facilities": accom["facilities"],
            "score": round(total, 3),
            "breakdown": breakdown,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"recommendations": scored})


@app.route("/accommodations/<int:accommodation_id>/similar", methods=["GET"])
def similarity_match(accommodation_id):
    all_accoms, status = db_get("/internal/accommodations-with-price")
    if status >= 400:
        return jsonify(all_accoms), status

    target = next((a for a in all_accoms if a["accommodation_id"] == accommodation_id), None)
    if target is None:
        return jsonify({"error": "not found"}), 404

    def similarity(a):
        same_city = 1 if a["city_area"] == target["city_area"] else 0
        facility_overlap = len(set(a["facilities"]) & set(target["facilities"]))
        price_diff = abs(a["min_price"] - target["min_price"])
        return same_city * 3 + facility_overlap - (price_diff / 20)

    others = [a for a in all_accoms if a["accommodation_id"] != accommodation_id]
    others.sort(key=similarity, reverse=True)

    return jsonify([{
        "accommodation_id": a["accommodation_id"],
        "name": a["name"],
        "city_area": a["city_area"],
        "starting_price": a["min_price"],
    } for a in others[:4]])


# ===================== AI: EXPLANATIONS (unchanged — no DB access needed) =====================

@app.route("/recommendations/explain", methods=["POST"])
def explain_recommendation():
    data = request.get_json() or {}
    name = data.get("name", "this accommodation")
    city = data.get("city_area", "")
    price = data.get("starting_price")
    rating = data.get("avg_rating")
    reviews = data.get("review_count")
    facilities = ", ".join(data.get("facilities", [])) or "none listed"
    score = data.get("score")
    match_pct = round((score or 0) * 100)

    question = (
        f"Here is DATA about one accommodation. Only use the numbers given below — "
        f"do not invent, estimate, or assume any other numbers (no averages, no comparisons "
        f"to other listings, nothing not listed here).\n\n"
        f"Name: {name}\n"
        f"Location: {city}\n"
        f"Price: ${price}/night\n"
        f"Rating: {rating}★ from {reviews} reviews\n"
        f"Facilities: {facilities}\n"
        f"Overall match: {match_pct}%\n\n"
        "Write 2 - 3 long sentence highlighting a real standout detail "
        "about this accommodation — its actual price, rating, or a notable facility. "
        "Do not mention the overall match percentage as if it were a fact about the "
        "place itself (e.g. don't say 'this place has a 63% rating') — that number is "
        "a ranking score, not a property of the accommodation."
        "Instead explain how it matches to that score."
    )

    app.logger.info("explain prompt:\n%s", question)

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a friendly travel assistant. You only restate and lightly "
                        "rephrase the facts you are given. You never invent statistics, "
                        "averages, or details not present in the user's message. "
                        "Answer in 2 - 3 long conversational sentence."
                    )
                },
                {"role": "user", "content": question}
            ],
            max_tokens=200,
            temperature=0.2,
        )
        explanation = response.choices[0].message.content
        return jsonify({"explanation": explanation})
    except Exception as exc:
        return jsonify({
            "error": "Local AI agent request failed. Check that Ollama is running and that "
                     f"{OLLAMA_MODEL} is installed.",
            "detail": str(exc)
        }), 503


@app.route("/recommendations/explain-compare", methods=["POST"])
def explain_compare():
    data = request.get_json() or {}
    items = data.get("items", [])

    if not items:
        return jsonify({"error": "items are required"}), 400

    lines = []
    for it in items:
        facilities = ", ".join(it.get("facilities", [])) or "none listed"
        match_pct = round((it.get("score") or 0) * 100)
        it["_match_pct"] = match_pct
        lines.append(
            f"- {it.get('name')}: ${it.get('starting_price')}/night in {it.get('city_area')}, "
            f"★{it.get('avg_rating')} ({it.get('review_count')} reviews), facilities: {facilities}, "
            f"overall match: {match_pct}%"
        )

    winner = max(items, key=lambda it: it.get("score") or 0)
    winner_name = winner.get("name")
    winner_pct = winner["_match_pct"]

    question = (
        "Here is DATA about accommodation options a traveler is comparing. "
        "Only use the numbers given below — do not invent, estimate, or assume any "
        "other numbers (no 'average price', no 'average match', nothing not listed here).\n\n"
        + "\n".join(lines) +
        f"\n\nFACT (already calculated, do not recalculate or contradict this): "
        f"the option with the highest overall match is \"{winner_name}\" at {winner_pct}%.\n\n"
        "Write 2-3 conversational sentences comparing these options using ONLY their real "
        "price, rating, and facilities listed above. End by naming the option with the highest "
        f"overall match — it is \"{winner_name}\" — and briefly say why, based only on the data given."
    )

    app.logger.info("explain-compare prompt:\n%s", question)

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a travel assistant. You only restate and lightly rephrase the "
                        "numbers you are given. You never invent statistics, averages, or facts "
                        "not present in the user's message. You never do your own numeric comparisons — "
                        "if a comparison result is given to you as a fact, you repeat it, you do not recompute it."
                    )
                },
                {"role": "user", "content": question}
            ],
            max_tokens=250,
            temperature=0.2,
        )
        return jsonify({"explanation": response.choices[0].message.content})
    except Exception as exc:
        return jsonify({
            "error": "Local AI agent request failed. Check that Ollama is running and that "
                     f"{OLLAMA_MODEL} is installed.",
            "detail": str(exc)
        }), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)