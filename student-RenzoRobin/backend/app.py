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
    # timeout: wait up to 10s for a lock to clear instead of failing instantly
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # readers don't block writers
    return conn


def init_db():
    conn = get_db()
    try:
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())
        conn.commit()

        count = conn.execute("SELECT COUNT(*) AS c FROM accommodations").fetchone()["c"]
        if count == 0:
            seed_data(conn)
    finally:
        conn.close()

def seed_data(conn):
    accommodations = [
        # ---- Bali, Indonesia ----
        ("Ubud Riverside Villa", "Bali, Indonesia", "A quiet villa in Ubud beside a working rice terrace, ten minutes from central Ubud.", ["wifi", "pool", "breakfast"], 4.8, 210),
        ("Ubud Rice Terrace Bungalow", "Bali, Indonesia", "Wooden bungalow in Ubud overlooking Tegallalang, popular with couples.", ["wifi", "breakfast"], 4.6, 88),
        ("Ubud Forest Eco Lodge", "Bali, Indonesia", "Sustainable lodge in Ubud near the Monkey Forest, solar-powered.", ["wifi", "parking"], 4.5, 54),
        ("Ubud Art House Homestay", "Bali, Indonesia", "Family homestay in Ubud run by local painters, walk to the art market.", ["wifi", "breakfast"], 4.7, 41),
        ("Ubud Yoga Retreat Room", "Bali, Indonesia", "Simple room in Ubud attached to a daily yoga studio.", ["wifi"], 4.4, 63),
        ("Ubud Palace View Suite", "Bali, Indonesia", "Suite overlooking the Ubud Water Palace courtyard.", ["wifi", "pool", "breakfast", "parking"], 4.9, 132),
        ("Ubud Jungle Pool Villa", "Bali, Indonesia", "Private pool villa in Ubud surrounded by jungle canopy.", ["wifi", "pool", "parking"], 4.8, 176),
        ("Ubud Backpacker Hostel", "Bali, Indonesia", "Budget dorms and privates in Ubud, five minutes from the market.", ["wifi"], 3.8, 310),
        ("Ubud Organic Farmstay", "Bali, Indonesia", "Stay on a working organic farm near Ubud with cooking classes.", ["wifi", "breakfast"], 4.6, 47),
        ("Ubud Central Boutique Inn", "Bali, Indonesia", "Small boutique inn right on Ubud's Monkey Forest Road.", ["wifi", "breakfast", "parking"], 4.3, 120),

        # ---- Kyoto, Japan ----
        ("Kyoto Machiya Townhouse", "Kyoto, Japan", "Restored wooden machiya near Gion, with a private tsuboniwa garden.", ["wifi", "parking"], 4.8, 150),
        ("Kyoto Station Capsule Inn", "Kyoto, Japan", "Compact capsule stay two minutes from Kyoto Station.", ["wifi"], 4.0, 260),
        ("Kyoto Riverside Ryokan", "Kyoto, Japan", "Traditional ryokan on the Kamo River with kaiseki breakfast.", ["wifi", "breakfast"], 4.9, 98),
        ("Kyoto Zen Garden Inn", "Kyoto, Japan", "Quiet inn near a temple complex, tatami rooms.", ["wifi", "breakfast"], 4.7, 74),
        ("Kyoto Modern Loft", "Kyoto, Japan", "Renovated loft in Nakagyo, walkable to Nishiki Market.", ["wifi", "parking"], 4.5, 112),
        ("Kyoto Bamboo Grove Cottage", "Kyoto, Japan", "Small cottage near Arashiyama's bamboo grove.", ["wifi"], 4.6, 65),
        ("Kyoto Family Guesthouse", "Kyoto, Japan", "Two-room guesthouse suited to families, close to Nijo Castle.", ["wifi", "breakfast", "parking"], 4.4, 58),
        ("Kyoto Budget Hostel", "Kyoto, Japan", "Simple dorms and privates near Kawaramachi's shopping streets.", ["wifi"], 3.9, 225),
        ("Kyoto Temple View Suite", "Kyoto, Japan", "Suite with a rooftop view toward Higashiyama's temples.", ["wifi", "breakfast"], 4.8, 83),
        ("Kyoto Onsen Ryokan", "Kyoto, Japan", "Ryokan with a small private onsen bath.", ["wifi", "pool", "breakfast"], 4.9, 140),

        # ---- Lisbon, Portugal ----
        ("Lisbon Alfama Loft", "Lisbon, Portugal", "Tiled loft in the Alfama district with tram views from the window.", ["wifi"], 4.5, 105),
        ("Lisbon Riverside Apartment", "Lisbon, Portugal", "Apartment overlooking the Tagus, near Cais do Sodré.", ["wifi", "parking"], 4.6, 92),
        ("Lisbon Bairro Alto Studio", "Lisbon, Portugal", "Studio steps from Bairro Alto's bars and restaurants.", ["wifi"], 4.2, 178),
        ("Lisbon Belem Guesthouse", "Lisbon, Portugal", "Family-run guesthouse near the Jerónimos Monastery.", ["wifi", "breakfast"], 4.7, 63),
        ("Lisbon Rooftop Pool Suite", "Lisbon, Portugal", "Suite with rooftop pool access and city views.", ["wifi", "pool", "breakfast"], 4.8, 141),
        ("Lisbon Budget Hostel", "Lisbon, Portugal", "Social hostel near Rossio Square, popular with backpackers.", ["wifi"], 3.9, 302),
        ("Lisbon Principe Real Flat", "Lisbon, Portugal", "Design-forward flat in the trendy Príncipe Real area.", ["wifi", "parking"], 4.6, 87),
        ("Lisbon Ocean View Villa", "Lisbon, Portugal", "Villa on the coast near Cascais, short drive from the city.", ["wifi", "pool", "parking"], 4.9, 55),
        ("Lisbon Historic Center Room", "Lisbon, Portugal", "Simple room in a converted 18th-century building downtown.", ["wifi", "breakfast"], 4.3, 130),
        ("Lisbon Family Townhouse", "Lisbon, Portugal", "Multi-room townhouse suited to families or groups.", ["wifi", "breakfast", "parking"], 4.5, 44),
    ]

    accom_ids = []
    for name, city, desc, facilities, rating, reviews in accommodations:
        cur = conn.execute(
            "INSERT INTO accommodations (name, city_area, description, facilities, images, avg_rating, review_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, city, desc, json.dumps(facilities), json.dumps([]), rating, reviews)
        )
        accom_ids.append(cur.lastrowid)

    # 30 base prices, roughly cheap→expensive within each area
    room_prices = [
        65, 55, 40, 35, 30, 95, 110, 18, 32, 60,        # Ubud, Bali
        70, 25, 130, 85, 60, 55, 45, 20, 100, 150,      # Kyoto
        50, 90, 35, 65, 140, 22, 95, 160, 45, 70,       # Lisbon
    ]
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

@app.route("/areas", methods=["GET"])
def list_areas():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT city_area FROM accommodations ORDER BY city_area"
        ).fetchall()
    finally:
        conn.close()
    return jsonify([r["city_area"] for r in rows])

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
    try:
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
    finally:
        conn.close()
    return jsonify({"accommodation_id": new_id}), 201


@app.route("/accommodations", methods=["GET"])
def list_accommodations():
    city = request.args.get("city")
    facility = request.args.get("facility")

    conn = get_db()
    try:
        query = "SELECT * FROM accommodations"
        params = []
        if city:
            query += " WHERE city_area LIKE ?"
            params.append(f"%{city}%")

        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    results = [accommodation_to_dict(r) for r in rows]
    if facility:
        results = [r for r in results if facility in r["facilities"]]
    return jsonify(results)


@app.route("/accommodations/<int:accommodation_id>", methods=["GET"])
def get_accommodation(accommodation_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM accommodations WHERE accommodation_id = ?", (accommodation_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(accommodation_to_dict(row))


@app.route("/accommodations/<int:accommodation_id>", methods=["PUT"])
def update_accommodation(accommodation_id):
    data = request.get_json()
    conn = get_db()
    try:
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
    finally:
        conn.close()
    return jsonify({"updated": accommodation_id})


@app.route("/accommodations/<int:accommodation_id>", methods=["DELETE"])
def delete_accommodation(accommodation_id):
    conn = get_db()
    try:
        # Cascade manually: schema has no ON DELETE CASCADE, and FKs are enforced.
        # Order matters — children of children first.
        conn.execute("DELETE FROM list_accommodations WHERE accommodation_id = ?", (accommodation_id,))
        conn.execute("DELETE FROM room_types WHERE accommodation_id = ?", (accommodation_id,))
        conn.execute("DELETE FROM accommodations WHERE accommodation_id = ?", (accommodation_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": accommodation_id})


# ===================== ROOM TYPES CRUD =====================

@app.route("/accommodations/<int:accommodation_id>/rooms", methods=["POST"])
def create_room(accommodation_id):
    data = request.get_json()
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO room_types (accommodation_id, room_name, price_per_night, available_rooms, capacity, images) VALUES (?, ?, ?, ?, ?, ?)",
            (
                accommodation_id, data.get("room_name"), data.get("price_per_night"),
                data.get("available_rooms", 1), data.get("capacity", 2), json.dumps(data.get("images", [])),
            )
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    return jsonify({"room_id": new_id}), 201


@app.route("/accommodations/<int:accommodation_id>/rooms", methods=["GET"])
def list_rooms(accommodation_id):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM room_types WHERE accommodation_id = ?", (accommodation_id,)).fetchall()
    finally:
        conn.close()
    return jsonify([room_to_dict(r) for r in rows])


@app.route("/rooms/<int:room_id>", methods=["GET"])
def get_room(room_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM room_types WHERE room_id = ?", (room_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(room_to_dict(row))


@app.route("/rooms/<int:room_id>", methods=["PUT"])
def update_room(room_id):
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "UPDATE room_types SET room_name = ?, price_per_night = ?, available_rooms = ?, capacity = ?, images = ? WHERE room_id = ?",
            (
                data.get("room_name"), data.get("price_per_night"), data.get("available_rooms"),
                data.get("capacity"), json.dumps(data.get("images", [])), room_id,
            )
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"updated": room_id})


@app.route("/rooms/<int:room_id>", methods=["DELETE"])
def delete_room(room_id):
    conn = get_db()
    try:
        # A room can be referenced by list_accommodations.room_id
        conn.execute("UPDATE list_accommodations SET room_id = NULL WHERE room_id = ?", (room_id,))
        conn.execute("DELETE FROM room_types WHERE room_id = ?", (room_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": room_id})


# ===================== PRIORITIES CRUD =====================

@app.route("/priorities", methods=["POST"])
def create_priority():
    data = request.get_json()
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO priorities (user_id, price_weight, location_weight, facility_weight, review_weight) VALUES (?, ?, ?, ?, ?)",
            (
                data.get("user_id"), data.get("price_weight", 50), data.get("location_weight", 50),
                data.get("facility_weight", 50), data.get("review_weight", 50),
            )
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    return jsonify({"priority_id": new_id}), 201


@app.route("/priorities/<int:user_id>", methods=["GET"])
def get_priority(user_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM priorities WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
    finally:
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
    try:
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
    finally:
        conn.close()
    return jsonify({"updated_user_id": user_id})


@app.route("/priorities/<int:user_id>", methods=["DELETE"])
def delete_priority(user_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM priorities WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted_user_id": user_id})


# ===================== LISTS CRUD =====================

@app.route("/lists", methods=["POST"])
def create_list():
    data = request.get_json()
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO lists (user_id, list_name) VALUES (?, ?)",
            (data.get("user_id"), data.get("list_name", "My list"))
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    return jsonify({"list_id": new_id}), 201


@app.route("/lists/<int:user_id>", methods=["GET"])
def get_user_lists(user_id):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM lists WHERE user_id = ?", (user_id,)).fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/lists/<int:list_id>", methods=["PUT"])
def rename_list(list_id):
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute("UPDATE lists SET list_name = ? WHERE list_id = ?", (data.get("list_name"), list_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"updated": list_id})


@app.route("/lists/<int:list_id>", methods=["DELETE"])
def delete_list(list_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM list_accommodations WHERE list_id = ?", (list_id,))
        conn.execute("DELETE FROM lists WHERE list_id = ?", (list_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": list_id})


# ===================== LIST ACCOMMODATIONS CRUD (many-to-many) =====================

@app.route("/lists/<int:list_id>/accommodations", methods=["POST"])
def add_to_list(list_id):
    data = request.get_json()
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO list_accommodations (list_id, accommodation_id, room_id, status) VALUES (?, ?, ?, ?)",
            (list_id, data.get("accommodation_id"), data.get("room_id"), data.get("status", "Option"))
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    return jsonify({"list_accom_id": new_id}), 201


@app.route("/lists/<int:list_id>/accommodations", methods=["GET"])
def get_list_accommodations(list_id):
    status = request.args.get("status")

    conn = get_db()
    try:
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
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/list-accommodations/<int:list_accom_id>", methods=["PUT"])
def update_list_accommodation(list_accom_id):
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "UPDATE list_accommodations SET status = ?, room_id = ? WHERE list_accom_id = ?",
            (data.get("status"), data.get("room_id"), list_accom_id)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"updated": list_accom_id})


@app.route("/list-accommodations/<int:list_accom_id>", methods=["DELETE"])
def remove_from_list(list_accom_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM list_accommodations WHERE list_accom_id = ?", (list_accom_id,))
        conn.commit()
    finally:
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
    try:
        weights_row = conn.execute(
            "SELECT * FROM priorities WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)
        ).fetchone()
        weights = dict(weights_row) if weights_row else {
            "price_weight": 50, "location_weight": 50, "facility_weight": 50, "review_weight": 50
        }

        all_accoms = fetch_accommodations_with_price(conn)
    finally:
        conn.close()

    # Only show listings in the area the user picked
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
    conn = get_db()
    try:
        all_accoms = fetch_accommodations_with_price(conn)
    finally:
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
        it["_match_pct"] = match_pct  # stash for the winner calc below
        lines.append(
            f"- {it.get('name')}: ${it.get('starting_price')}/night in {it.get('city_area')}, "
            f"★{it.get('avg_rating')} ({it.get('review_count')} reviews), facilities: {facilities}, "
            f"overall match: {match_pct}%"
        )

    # Compute the winner ourselves — don't trust the model to compare numbers
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

# ===================== ENTRY POINT =====================

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)