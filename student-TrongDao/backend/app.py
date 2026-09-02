import os
import requests
import json
from datetime import datetime, timezone
from flask_cors import CORS
from flask import Flask, render_template, jsonify, request

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)

CORS(app)

DATABASE_API_URL = os.getenv(
    "DATABASE_API_URL",
    "http://localhost:5404"
)


OLLAMA_API_URL = os.getenv(
    "OLLAMA_API_URL",
    "http://localhost:11434"
)


OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:0.5b"
)


OLLAMA_REVIEW_MODEL = os.getenv(
    "OLLAMA_REVIEW_MODEL",
    "llama3.1:8b"
)


def call_ollama(system_prompt, user_prompt, model):
    response = requests.post(
        f"{OLLAMA_API_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "stream": False
        },
        timeout=180
    )

    response.raise_for_status()

    response_data = response.json()

    return response_data["message"]["content"]


def record_workflow_step(workflow_log, journey_id, phase, status, details):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "journey_id": journey_id,
        "phase": phase,
        "status": status,
        "details": details
    }

    workflow_log.append(entry)

    print(
        "AGENTIC_WORKFLOW "
        + json.dumps(entry),
        flush=True
    )


def create_ai_explanation(preferences, recommendations):
    system_prompt = """
You are the JourneyBuddy attraction recommendation assistant.
Explain why the provided attractions suit the traveller.
Use only the supplied attraction data.
Do not invent attractions, prices, facilities, or other facts.
Keep the response concise and beginner-friendly.
"""

    prompt_data = {
        "traveller_preferences": {
            "destination_city": preferences["destination_city"],
            "interests": preferences["interests"],
            "weather_preferences": preferences[
                "weather_preferences"
            ],
            "crowd_tolerance": preferences["crowd_tolerance"],
            "budget_range": preferences["budget_range"],
            "accessibility_needs": preferences[
                "accessibility_needs"
            ]
        },
        "recommended_attractions": recommendations
    }

    user_prompt = (
        "Explain these evidence-based recommendations:\n"
        + json.dumps(prompt_data, indent=2)
    )

    return call_ollama(
        system_prompt,
        user_prompt,
        OLLAMA_MODEL
    )


def review_ai_explanation(preferences, recommendations, draft_explanation):
    system_prompt = """
You are the JourneyBuddy review agent.
Review the draft recommendation explanation against the supplied
database evidence.
Remove or correct every unsupported claim.
Do not invent locations, categories, prices, facilities, suitability,
accessibility details, or traveller information.
Return only the corrected final explanation.
Keep it concise and beginner-friendly.
"""

    review_data = {
        "traveller_preferences": preferences,
        "database_recommendations": recommendations,
        "qwen_draft": draft_explanation
    }

    user_prompt = (
        "Review and correct this recommendation:\n"
        + json.dumps(review_data, indent=2)
    )

    return call_ollama(
        system_prompt,
        user_prompt,
        OLLAMA_REVIEW_MODEL
    )


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok", "student": "4: TrongDao"}


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

        top_recommendations = recommendations[:5]

        ai_mode = data.get("ai_mode", False)

        ai_draft = None
        ai_review = None
        ai_explanation = None
        ai_error = None
        review_error = None
        workflow_log = []

        if ai_mode:
            record_workflow_step(
                workflow_log,
                data["journey_id"],
                "PLAN",
                "completed",
                (
                    "Validated the traveller preferences and planned "
                    "an evidence-based attraction recommendation."
                )
            )

            record_workflow_step(
                workflow_log,
                data["journey_id"],
                "ACT",
                "completed",
                (
                    f"Retrieved {len(places)} database attractions, "
                    f"applied the ranking rules, and selected "
                    f"{len(top_recommendations)} recommendations."
                )
            )

            if top_recommendations:
                try:
                    ai_draft = create_ai_explanation(
                        data,
                        top_recommendations
                    )

                    ai_explanation = ai_draft

                    record_workflow_step(
                        workflow_log,
                        data["journey_id"],
                        "OBSERVE",
                        "completed",
                        (
                            f"{OLLAMA_MODEL} generated an explanation "
                            "for the database-backed recommendations."
                        )
                    )

                except requests.RequestException as error:
                    ai_error = (
                        "Qwen is unavailable. "
                        "The data-based recommendations are still valid."
                    )

                    record_workflow_step(
                        workflow_log,
                        data["journey_id"],
                        "OBSERVE",
                        "failed",
                        f"Qwen request failed: {error}"
                    )

                if ai_draft:
                    try:
                        ai_review = review_ai_explanation(
                            data,
                            top_recommendations,
                            ai_draft
                        )

                        ai_explanation = ai_review

                        record_workflow_step(
                            workflow_log,
                            data["journey_id"],
                            "REVIEW",
                            "completed",
                            (
                                f"{OLLAMA_REVIEW_MODEL} reviewed and "
                                "corrected the Qwen explanation."
                            )
                        )

                    except requests.RequestException as error:
                        review_error = (
                            "Llama review is unavailable. "
                            "The displayed AI explanation is unreviewed."
                        )

                        record_workflow_step(
                            workflow_log,
                            data["journey_id"],
                            "REVIEW",
                            "failed",
                            f"Llama review failed: {error}"
                        )

            else:
                record_workflow_step(
                    workflow_log,
                    data["journey_id"],
                    "OBSERVE",
                    "completed",
                    "No attractions matched the traveller preferences."
                )

            if ai_review:
                adapt_details = (
                    "Used the Llama-reviewed explanation as the final "
                    "AI response."
                )

            elif ai_draft:
                adapt_details = (
                    "Used the Qwen draft with an unreviewed warning "
                    "because the review agent was unavailable."
                )

            else:
                adapt_details = (
                    "Returned the deterministic database results "
                    "without an AI explanation."
                )

            record_workflow_step(
                workflow_log,
                data["journey_id"],
                "ADAPT",
                "completed",
                adapt_details
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
            "mode": "ai" if ai_mode else "data",
            "implementation_model": (
                OLLAMA_MODEL if ai_mode else None
            ),
            "review_model": (
                OLLAMA_REVIEW_MODEL if ai_mode else None
            ),
            "ai_draft": ai_draft,
            "ai_review": ai_review,
            "ai_explanation": ai_explanation,
            "ai_error": ai_error,
            "review_error": review_error,
            "recommendation_count": len(top_recommendations),
            "recommendations": top_recommendations,
            "agentic_workflow": workflow_log
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
    port = int(os.getenv("PORT", "5004"))
    app.run(host="0.0.0.0", port=port)
