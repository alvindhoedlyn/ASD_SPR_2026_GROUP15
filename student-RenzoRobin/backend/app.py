import json
import os
import sqlite3
import datetime
from openai import OpenAI
from flask import Flask, render_template, request, jsonify

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "instance", "app.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://ai-mode:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")

client = OpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama")


# ===================== DATABASE =====================

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM accommodations").fetchone()["c"]
    if count == 0:
        seed_data(conn)

    conn.close()


def seed_data(conn):
    accommodations = [
        ("Ubud Riverside Villa", "Ubud, Bali", "A quiet villa beside a working rice terrace, ten minutes from central Ubud.", ["wifi", "pool", "breakfast"], 4.8, 210),
        ("Seminyak Beach Stay", "Seminyak, Bali", "Steps from the sand, with rooftop sunset views and an on-site restaurant.", ["wifi", "pool", "parking", "breakfast"], 4.6, 340),
        ("Canggu Surf Loft", "Canggu, Bali", "Minimalist loft popular with surfers, walkable to the main breaks.", ["wifi", "parking"], 4.4, 95),
        ("Sanur Garden House", "Sanur, Bali", "Family-run guesthouse with a lush courtyard garden and quiet street.", ["wifi", "breakfast"], 4.7, 60),
        ("Uluwatu Cliffside Retreat", "Uluwatu, Bali", "Clifftop stay with ocean views, a short drive from the temple.", ["wifi", "pool", "parking"], 4.9, 150),
        ("Kuta Central Inn", "Kuta, Bali", "Budget-friendly and central, close to shopping and nightlife.", ["wifi"], 3.9, 420),
        ("Jimbaran Bay Cottage", "Jimbaran, Bali", "Beachfront cottage near the seafood market, quiet at night.", ["wifi", "breakfast", "parking"], 4.5, 130),
        ("Nusa Dua Resort Room", "Nusa Dua, Bali", "Resort-style room with pool access and a private beach club.", ["wifi", "pool", "breakfast"], 4.6, 280),
        ("Denpasar City Studio", "Denpasar, Bali", "Compact studio close to the airport, good for short layovers.", ["wifi", "parking"], 4.0, 75),
        ("Amed Dive Lodge", "Amed, Bali", "Simple lodge popular with divers, near several dive shops.", ["wifi"], 4.3, 40),
    ]

    accom_ids = []
    for name, city, desc, facilities, rating, reviews in accommodations:
        cur = conn.execute(
            "INSERT INTO accommodations (name, city_area, description, facilities, images, avg_rating, review_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, city, desc, json.dumps(facilities), json.dumps([]), rating, reviews)
        )
        accom_ids.append(cur.lastrowid)

    room_prices = [65, 80, 45, 38, 110, 22, 55, 90, 30, 40]
    for accom_id, price in zip(accom_ids, room_prices):
        conn.execute(
            "INSERT INTO room_types (accommodation_id, room_name, price_per_night, available_rooms, capacity, images) VALUES (?, ?, ?, ?, ?, ?)",
            (accom_id, "Standard room", price, 3, 2, json.dumps([]))
        )
        conn.execute(
            "INSERT INTO room_types (accommodation_id, room_name, price_per_night, available_rooms, capacity, images) VALUES (?, ?, ?, ?, ?, ?)",
            (accom_id, "Deluxe room", round(price * 1.4, 2), 2, 3, json.dumps([]))
        )

    conn.commit()


def accommodation_to_dict(row):
    d = dict(row)
    d["facilities"] = json.loads(d["facilities"] or "[]")
    d["images"] = json.loads(d["images"] or "[]")
    return d


def room_to_dict(row):
    d = dict(row)
    d["images"] = json.loads(d["images"] or "[]")
    return d


# ===================== PAGES =====================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok", "service": "accommodation-recommender"}


# ===================== ACCOMMODATIONS CRUD =====================

@app.route("/accommodations", methods=["POST"])
def create_accommodation():
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO accommodations (name, city_area, description, facilities, images, avg_rating, review_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            data.get("name"), data.get("city_area"), data.get("description"),
            json.dumps(data.get("facilities", [])), json.dumps(data.get("images", [])),
            data.get("avg_rating", 0), data.get("review_count", 0),
        )
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"accommodation_id": new_id}), 201


@app.route("/accommodations", methods=["GET"])
def list_accommodations():
    city = request.args.get("city")
    facility = request.args.get("facility")

    conn = get_db()
    query = "SELECT * FROM accommodations"
    params = []
    if city:
        query += " WHERE city_area LIKE ?"
        params.append(f"%{city}%")

    rows = conn.execute(query, params).fetchall()
    conn.close()

    results = [accommodation_to_dict(r) for r in rows]
    if facility:
        results = [r for r in results if facility in r["facilities"]]
    return jsonify(results)


@app.route("/accommodations/<int:accommodation_id>", methods=["GET"])
def get_accommodation(accommodation_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM accommodations WHERE accommodation_id = ?", (accommodation_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(accommodation_to_dict(row))


@app.route("/accommodations/<int:accommodation_id>", methods=["PUT"])
def update_accommodation(accommodation_id):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        """UPDATE accommodations
           SET name = ?, city_area = ?, description = ?, facilities = ?, images = ?, avg_rating = ?, review_count = ?
           WHERE accommodation_id = ?""",
        (
            data.get("name"), data.get("city_area"), data.get("description"),
            json.dumps(data.get("facilities", [])), json.dumps(data.get("images", [])),
            data.get("avg_rating", 0), data.get("review_count", 0), accommodation_id,
        )
    )
    conn.commit()
    conn.close()
    return jsonify({"updated": accommodation_id})


@app.route("/accommodations/<int:accommodation_id>", methods=["DELETE"])
def delete_accommodation(accommodation_id):
    conn = get_db()
    conn.execute("DELETE FROM accommodations WHERE accommodation_id = ?", (accommodation_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": accommodation_id})


# ===================== ROOM TYPES CRUD =====================

@app.route("/accommodations/<int:accommodation_id>/rooms", methods=["POST"])
def create_room(accommodation_id):
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO room_types (accommodation_id, room_name, price_per_night, available_rooms, capacity, images) VALUES (?, ?, ?, ?, ?, ?)",
        (
            accommodation_id, data.get("room_name"), data.get("price_per_night"),
            data.get("available_rooms", 1), data.get("capacity", 2), json.dumps(data.get("images", [])),
        )
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"room_id": new_id}), 201


@app.route("/accommodations/<int:accommodation_id>/rooms", methods=["GET"])
def list_rooms(accommodation_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM room_types WHERE accommodation_id = ?", (accommodation_id,)).fetchall()
    conn.close()
    return jsonify([room_to_dict(r) for r in rows])


@app.route("/rooms/<int:room_id>", methods=["GET"])
def get_room(room_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM room_types WHERE room_id = ?", (room_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(room_to_dict(row))


@app.route("/rooms/<int:room_id>", methods=["PUT"])
def update_room(room_id):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "UPDATE room_types SET room_name = ?, price_per_night = ?, available_rooms = ?, capacity = ?, images = ? WHERE room_id = ?",
        (
            data.get("room_name"), data.get("price_per_night"), data.get("available_rooms"),
            data.get("capacity"), json.dumps(data.get("images", [])), room_id,
        )
    )
    conn.commit()
    conn.close()
    return jsonify({"updated": room_id})


@app.route("/rooms/<int:room_id>", methods=["DELETE"])
def delete_room(room_id):
    conn = get_db()
    conn.execute("DELETE FROM room_types WHERE room_id = ?", (room_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": room_id})


# ===================== PRIORITIES CRUD =====================

@app.route("/priorities", methods=["POST"])
def create_priority():
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO priorities (user_id, price_weight, location_weight, facility_weight, review_weight) VALUES (?, ?, ?, ?, ?)",
        (
            data.get("user_id"), data.get("price_weight", 50), data.get("location_weight", 50),
            data.get("facility_weight", 50), data.get("review_weight", 50),
        )
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"priority_id": new_id}), 201


@app.route("/priorities/<int:user_id>", methods=["GET"])
def get_priority(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM priorities WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({
            "user_id": user_id, "price_weight": 50, "location_weight": 50,
            "facility_weight": 50, "review_weight": 50,
        })
    return jsonify(dict(row))


@app.route("/priorities/<int:user_id>", methods=["PUT"])
def update_priority(user_id):
    data = request.get_json()
    conn = get_db()
    existing = conn.execute("SELECT * FROM priorities WHERE user_id = ?", (user_id,)).fetchone()

    if existing:
        conn.execute(
            "UPDATE priorities SET price_weight = ?, location_weight = ?, facility_weight = ?, review_weight = ?, updated_at = ? WHERE user_id = ?",
            (
                data.get("price_weight", 50), data.get("location_weight", 50),
                data.get("facility_weight", 50), data.get("review_weight", 50),
                datetime.datetime.utcnow().isoformat(), user_id,
            )
        )
    else:
        conn.execute(
            "INSERT INTO priorities (user_id, price_weight, location_weight, facility_weight, review_weight) VALUES (?, ?, ?, ?, ?)",
            (user_id, data.get("price_weight", 50), data.get("location_weight", 50), data.get("facility_weight", 50), data.get("review_weight", 50))
        )

    conn.commit()
    conn.close()
    return jsonify({"updated_user_id": user_id})


@app.route("/priorities/<int:user_id>", methods=["DELETE"])
def delete_priority(user_id):
    conn = get_db()
    conn.execute("DELETE FROM priorities WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted_user_id": user_id})


# ===================== LISTS CRUD =====================

@app.route("/lists", methods=["POST"])
def create_list():
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO lists (user_id, list_name) VALUES (?, ?)",
        (data.get("user_id"), data.get("list_name", "My list"))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"list_id": new_id}), 201


@app.route("/lists/<int:user_id>", methods=["GET"])
def get_user_lists(user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM lists WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/lists/<int:list_id>", methods=["PUT"])
def rename_list(list_id):
    data = request.get_json()
    conn = get_db()
    conn.execute("UPDATE lists SET list_name = ? WHERE list_id = ?", (data.get("list_name"), list_id))
    conn.commit()
    conn.close()
    return jsonify({"updated": list_id})


@app.route("/lists/<int:list_id>", methods=["DELETE"])
def delete_list(list_id):
    conn = get_db()
    conn.execute("DELETE FROM list_accommodations WHERE list_id = ?", (list_id,))
    conn.execute("DELETE FROM lists WHERE list_id = ?", (list_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": list_id})


# ===================== LIST ACCOMMODATIONS CRUD (many-to-many) =====================

@app.route("/lists/<int:list_id>/accommodations", methods=["POST"])
def add_to_list(list_id):
    data = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO list_accommodations (list_id, accommodation_id, room_id, status) VALUES (?, ?, ?, ?)",
        (list_id, data.get("accommodation_id"), data.get("room_id"), data.get("status", "Option"))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"list_accom_id": new_id}), 201


@app.route("/lists/<int:list_id>/accommodations", methods=["GET"])
def get_list_accommodations(list_id):
    status = request.args.get("status")

    conn = get_db()
    query = """
        SELECT la.list_accom_id, la.status, la.added_at, la.room_id,
               a.accommodation_id, a.name, a.city_area, a.avg_rating
        FROM list_accommodations la
        JOIN accommodations a ON a.accommodation_id = la.accommodation_id
        WHERE la.list_id = ?
    """
    params = [list_id]
    if status:
        query += " AND la.status = ?"
        params.append(status)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/list-accommodations/<int:list_accom_id>", methods=["PUT"])
def update_list_accommodation(list_accom_id):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "UPDATE list_accommodations SET status = ?, room_id = ? WHERE list_accom_id = ?",
        (data.get("status"), data.get("room_id"), list_accom_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"updated": list_accom_id})


@app.route("/list-accommodations/<int:list_accom_id>", methods=["DELETE"])
def remove_from_list(list_accom_id):
    conn = get_db()
    conn.execute("DELETE FROM list_accommodations WHERE list_accom_id = ?", (list_accom_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": list_accom_id})


# ===================== AI: RECOMMENDATIONS =====================

def fetch_accommodations_with_price(conn):
    rows = conn.execute("""
        SELECT a.*, MIN(r.price_per_night) AS min_price
        FROM accommodations a
        LEFT JOIN room_types r ON r.accommodation_id = a.accommodation_id
        GROUP BY a.accommodation_id
    """).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["facilities"] = json.loads(d["facilities"] or "[]")
        d["min_price"] = d["min_price"] or 0
        results.append(d)
    return results


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

    conn = get_db()
    weights_row = conn.execute(
        "SELECT * FROM priorities WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)
    ).fetchone()
    weights = dict(weights_row) if weights_row else {
        "price_weight": 50, "location_weight": 50, "facility_weight": 50, "review_weight": 50
    }

    all_accoms = fetch_accommodations_with_price(conn)
    conn.close()

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
            "score": round(total, 3),
            "breakdown": breakdown,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"recommendations": scored})


@app.route("/accommodations/<int:accommodation_id>/similar", methods=["GET"])
def similarity_match(accommodation_id):
    conn = get_db()
    all_accoms = fetch_accommodations_with_price(conn)
    conn.close()

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


@app.route("/recommendations/explain", methods=["POST"])
def explain_recommendation():
    data = request.get_json() or {}
    accommodation_name = data.get("name", "this accommodation")
    breakdown = data.get("breakdown", {})

    question = (
        f"In one short sentence, explain why '{accommodation_name}' is a good match "
        f"given these scores (0-1 scale): price={breakdown.get('price_score')}, "
        f"location={breakdown.get('location_score')}, facilities={breakdown.get('facility_score')}, "
        f"reviews={breakdown.get('review_score')}. Be conversational, not technical."
    )

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a friendly travel assistant. "
                        "Answer in one short, conversational sentence."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
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


# ---------- Generic AI-mode chat endpoint (frontend -> backend -> Ollama -> LLM) ----------

@app.route("/ask", methods=["POST"])
def ask_local_agent():
    question = request.form.get("question", "").strip()
    if not question and request.is_json:
        question = (request.get_json() or {}).get("question", "").strip()

    if not question:
        return "<p>Question is required.</p>", 400

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise software engineering assistant. "
                        "Answer in one short paragraph unless asked otherwise."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            max_tokens=200,
            temperature=0.2,
        )

        answer = response.choices[0].message.content
        return f"<p>{answer}</p>"

    except Exception as exc:
        return (
            "<p>Local AI agent request failed. "
            f"Check that Ollama is running and that {OLLAMA_MODEL} is installed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )

@app.route("/recommendations/explain-compare", methods=["POST"])
def explain_compare():
    data = request.get_json() or {}
    items = data.get("items", [])  # [{name, breakdown}, ...]

    if not items:
        return jsonify({"error": "items are required"}), 400

    lines = []
    for it in items:
        b = it.get("breakdown", {})
        lines.append(
            f"- {it.get('name')}: price={b.get('price_score')}, "
            f"location={b.get('location_score')}, facilities={b.get('facility_score')}, "
            f"reviews={b.get('review_score')}"
        )

    question = (
        "Here are accommodation match scores (0-1 scale, higher is better) for a few options "
        f"being compared:\n" + "\n".join(lines) +
        "\n\nIn 2-3 short sentences, explain how they compare and why one might edge out "
        "the others, referencing the specific scores. Be conversational, not technical."
    )

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a friendly travel assistant. Be concise and specific."
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

# ===================== ENTRY POINT =====================

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)