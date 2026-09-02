import os
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)

DATABASE_API_URL = os.getenv(
    "DATABASE_API_URL",
    "http://localhost:5404"
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok", "student": "4"}


@app.route("/api/places", methods=["GET"])
def get_places():
    try:
        response = requests.get(
            f"{DATABASE_API_URL}/places",
            timeout=5
        )

        response.raise_for_status()

        return jsonify(response.json()), response.status_code

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not connect to the database service",
            "details": str(error)
        }), 503


@app.route("/api/recommendations", methods=["POST"])
def create_recommendations():
    data = request.get_json(silent=True) or {}

    required_fields = [
        "journey_id",
        "destination_city",
        "arrival_date",
        "departure_date",
        "interests",
        "weather_preferences",
        "crowd_tolerance",
        "budget_range",
        "accessibility_needs"
    ]

    missing_fields = []

    for field in required_fields:
        if field not in data or data[field] in (None, ""):
            missing_fields.append(field)

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    valid_crowd_levels = ["low", "medium", "high"]
    valid_budget_ranges = ["free", "low", "medium", "high"]

    if data["crowd_tolerance"] not in valid_crowd_levels:
        return jsonify({
            "error": "crowd_tolerance must be low, medium, or high"
        }), 400

    if data["budget_range"] not in valid_budget_ranges:
        return jsonify({
            "error": "budget_range must be free, low, medium, or high"
        }), 400

    try:
        places_response = requests.get(
            f"{DATABASE_API_URL}/places",
            timeout=5
        )

        places_response.raise_for_status()
        places = places_response.json()

        interests = data["interests"]

        if isinstance(interests, str):
            interest_list = interests.split(",")
        else:
            interest_list = interests

        cleaned_interests = []

        for interest in interest_list:
            cleaned_interests.append(interest.strip().lower())

        maximum_costs = {
            "free": 0,
            "low": 25,
            "medium": 60,
            "high": float("inf")
        }

        crowd_values = {
            "low": 1,
            "medium": 2,
            "high": 3
        }

        maximum_cost = maximum_costs[data["budget_range"]]
        user_crowd_tolerance = crowd_values[data["crowd_tolerance"]]
        weather_preference = data["weather_preferences"].lower()
        accessibility_needs = data["accessibility_needs"].lower()

        recommendations = []

        for place in places:
            if place["city"].lower() != data["destination_city"].lower():
                continue

            if place["estimated_cost"] > maximum_cost:
                continue

            score = place["beginner_friendliness_score"]
            reasons = [
                f"Beginner friendliness score: "
                f"{place['beginner_friendliness_score']}/5"
            ]

            if place["category"].lower() in cleaned_interests:
                score += 3
                reasons.append("Matches your interests")

            place_crowd_level = crowd_values[place["crowd_level"]]

            if place_crowd_level <= user_crowd_tolerance:
                score += 2
                reasons.append("Matches your crowd tolerance")

            if (
                "indoor" in weather_preference
                and place["indoor_outdoor"] in ["indoor", "both"]
            ):
                score += 1
                reasons.append("Matches your indoor preference")

            if (
                "outdoor" in weather_preference
                and place["indoor_outdoor"] in ["outdoor", "both"]
            ):
                score += 1
                reasons.append("Matches your outdoor preference")

            if (
                accessibility_needs not in ["none", "no", "not required"]
                and place["accessibility_information"] != "Not specified"
            ):
                score += 1
                reasons.append("Accessibility information is available")

            recommended_place = place.copy()
            recommended_place["recommendation_score"] = score
            recommended_place["recommendation_reasons"] = reasons

            recommendations.append(recommended_place)

        recommendations.sort(
            key=lambda place: (
                -place["recommendation_score"],
                place["estimated_cost"]
            )
        )

        request_record = {
            "journey_id": data["journey_id"],
            "destination_city": data["destination_city"],
            "arrival_date": data["arrival_date"],
            "departure_date": data["departure_date"],
            "interests": ", ".join(cleaned_interests),
            "weather_preferences": data["weather_preferences"],
            "crowd_tolerance": data["crowd_tolerance"],
            "budget_range": data["budget_range"],
            "accessibility_needs": data["accessibility_needs"],
            "status": "completed"
        }

        save_response = requests.post(
            f"{DATABASE_API_URL}/recommendation-requests",
            json=request_record,
            timeout=5
        )

        if not save_response.ok:
            return jsonify(save_response.json()), save_response.status_code

        saved_request = save_response.json()

        return jsonify({
            "request_id": saved_request["request_id"],
            "journey_id": data["journey_id"],
            "recommendation_count": len(recommendations[:5]),
            "recommendations": recommendations[:5]
        }), 200

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not communicate with the database service",
            "details": str(error)
        }), 503


@app.get("/api/saved-places")
def get_saved_places():
    journey_id = request.args.get("journey_id")

    if not journey_id:
        return jsonify({
            "error": "journey_id is required"
        }), 400

    try:
        response = requests.get(
            f"{DATABASE_API_URL}/saved-places",
            params={"journey_id": journey_id},
            timeout=5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not connect to the database service",
            "details": str(error)
        }), 503


@app.post("/api/saved-places")
def save_attraction():
    data = request.get_json(silent=True) or {}

    required_fields = [
        "attraction_id",
        "journey_id"
        ]

    missing_fields = []

    for field in required_fields:
        if field not in data or data[field] in (None, ""):
            missing_fields.append(field)
    
    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    try:
        response = requests.post(
            f"{DATABASE_API_URL}/saved-places",
            json={
                "journey_id": data["journey_id"],
                "attraction_id": data["attraction_id"],
                "notes": data.get("notes", "")
            },
            timeout = 5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not connect to the database service",
            "details": str(error)
        }), 503

    
@app.put("/api/saved-places/<int:saved_place_id>")
def update_saved_place(saved_place_id):
    data = request.get_json(silent=True) or {}

    required_fields = [
        "attraction_id",
        "journey_id"
    ]

    missing_fields = []
    
    for field in required_fields:
        if field not in data or data[field] in (None, ""):
            missing_fields.append(field)
        
    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    try:
        response = requests.put(
            f"{DATABASE_API_URL}/saved-places/{saved_place_id}",
            json={
                "journey_id": data["journey_id"],
                "attraction_id": data["attraction_id"],
                "notes": data.get("notes", "")
            }
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not connect to the database service",
            "details": str(error)    
        }), 503


@app.delete("/api/saved-places/<int:saved_place_id>")
def delete_saved_place(saved_place_id):
    try:
        response = requests.delete(
            f"{DATABASE_API_URL}/saved-places/{saved_place_id}",
            timeout= 5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not connect to the database service",
            "details": str(error)
        }), 503
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)
