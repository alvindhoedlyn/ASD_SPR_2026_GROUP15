import json
import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH = os.environ.get("DATABASE_PATH", "/app/database/data/accommodation.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")
PORT = int(os.environ.get("PORT", 6003))

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "method not allowed"}), 405

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not found"}), 404


# ===================== DATABASE =====================

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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

    room_prices = [
        65, 55, 40, 35, 30, 95, 110, 18, 32, 60,       # Ubud, Bali
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


def safe_json_load(raw_str, fallback):
    if not raw_str:
        return fallback
    try:
        return json.loads(raw_str)
    except (json.JSONDecodeError, TypeError):
        return fallback


def accommodation_to_dict(row):
    d = dict(row)
    d["facilities"] = safe_json_load(d.get("facilities"), [])
    d["images"] = safe_json_load(d.get("images"), [])
    return d


def room_to_dict(row):
    d = dict(row)
    d["images"] = safe_json_load(d.get("images"), [])
    return d


@app.route("/health")
def health():
    return {"status": "ok", "service": "database-api"}


# ===================== AREAS =====================

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


# ===================== ACCOMMODATIONS CRUD =====================

@app.route("/accommodations", methods=["POST"])
def create_accommodation():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("city_area"):
        return jsonify({"error": "name and city_area are required"}), 400
    
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO accommodations (name, city_area, description, facilities, images, avg_rating, review_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                data.get("name"),
                data.get("city_area"),
                data.get("description"),
                json.dumps(data.get("facilities", [])),
                json.dumps(data.get("images", [])),
                data.get("avg_rating", 0),
                data.get("review_count", 0),
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
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM accommodations WHERE accommodation_id = ?", (accommodation_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404

        conn.execute(
            """UPDATE accommodations
               SET name = ?, city_area = ?, description = ?, facilities = ?, images = ?, avg_rating = ?, review_count = ?
               WHERE accommodation_id = ?""",
            (
                data.get("name", row["name"]),
                data.get("city_area", row["city_area"]),
                data.get("description", row["description"]),
                json.dumps(data.get("facilities", safe_json_load(row["facilities"], []))),
                json.dumps(data.get("images", safe_json_load(row["images"], []))),
                data.get("avg_rating", row["avg_rating"]),
                data.get("review_count", row["review_count"]),
                accommodation_id,
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
        row = conn.execute("SELECT 1 FROM accommodations WHERE accommodation_id = ?", (accommodation_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        conn.execute("DELETE FROM accommodations WHERE accommodation_id = ?", (accommodation_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": accommodation_id})


# ===================== ROOM TYPES CRUD =====================

@app.route("/accommodations/<int:accommodation_id>/rooms", methods=["POST"])
def create_room(accommodation_id):
    data = request.get_json(silent=True) or {}
    price = data.get("price_per_night")
    if price is None or isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
        return jsonify({"error": "price_per_night must be greater than 0"}), 400

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO room_types (accommodation_id, room_name, price_per_night, available_rooms, capacity, images) VALUES (?, ?, ?, ?, ?, ?)",
            (
                accommodation_id,
                data.get("room_name"),
                price,
                data.get("available_rooms", 1),
                data.get("capacity", 2),
                json.dumps(data.get("images", [])),
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
    data = request.get_json(silent=True) or {}

    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM room_types WHERE room_id = ?", (room_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404

        # Enforce strict price validation
        if "price_per_night" in data:
            price = data["price_per_night"]
            if price is None or isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
                return jsonify({"error": "price_per_night must be greater than 0"}), 400
            new_price = price
        else:
            new_price = row["price_per_night"]

        new_name = data.get("room_name") or row["room_name"]
        new_avail = data.get("available_rooms") if data.get("available_rooms") is not None else row["available_rooms"]
        new_cap = data.get("capacity") if data.get("capacity") is not None else row["capacity"]
        raw_images = data.get("images")
        new_images = json.dumps(raw_images) if raw_images is not None else row["images"]

        conn.execute(
            """UPDATE room_types 
               SET room_name = ?, price_per_night = ?, available_rooms = ?, capacity = ?, images = ? 
               WHERE room_id = ?""",
            (new_name, new_price, new_avail, new_cap, new_images, room_id)
        )
        conn.commit()
    finally:
        conn.close()
        
    return jsonify({"updated": room_id}), 200


@app.route("/rooms/<int:room_id>", methods=["DELETE"])
def delete_room(room_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT 1 FROM room_types WHERE room_id = ?", (room_id,)).fetchone()
        if not row:
            return jsonify({"error": "Room not found"}), 404
        conn.execute("UPDATE list_accommodations SET room_id = NULL WHERE room_id = ?", (room_id,))
        conn.execute("DELETE FROM room_types WHERE room_id = ?", (room_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": room_id})


# ===================== PRIORITIES CRUD =====================

@app.route("/priorities", methods=["POST"])
def create_priority():
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO priorities (user_id, price_weight, location_weight, facility_weight, review_weight) VALUES (?, ?, ?, ?, ?)",
            (
                data.get("user_id"),
                data.get("price_weight", 50),
                data.get("location_weight", 50),
                data.get("facility_weight", 50),
                data.get("review_weight", 50),
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
            "user_id": user_id,
            "price_weight": 50,
            "location_weight": 50,
            "facility_weight": 50,
            "review_weight": 50,
        })
    return jsonify(dict(row))


@app.route("/priorities/<int:user_id>", methods=["PUT"])
def update_priority(user_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM priorities WHERE user_id = ?", (user_id,)).fetchone()
        now_str = datetime.now(timezone.utc).isoformat()
        if existing:
            conn.execute(
                "UPDATE priorities SET price_weight = ?, location_weight = ?, facility_weight = ?, review_weight = ?, updated_at = ? WHERE user_id = ?",
                (
                    data.get("price_weight", existing["price_weight"]),
                    data.get("location_weight", existing["location_weight"]),
                    data.get("facility_weight", existing["facility_weight"]),
                    data.get("review_weight", existing["review_weight"]),
                    now_str,
                    user_id,
                )
            )
        else:
            conn.execute(
                "INSERT INTO priorities (user_id, price_weight, location_weight, facility_weight, review_weight) VALUES (?, ?, ?, ?, ?)",
                (
                    user_id,
                    data.get("price_weight", 50),
                    data.get("location_weight", 50),
                    data.get("facility_weight", 50),
                    data.get("review_weight", 50),
                )
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"updated_user_id": user_id})


@app.route("/priorities/<int:user_id>", methods=["DELETE"])
def delete_priority(user_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT 1 FROM priorities WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        conn.execute("DELETE FROM priorities WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted_user_id": user_id})


# ===================== LISTS CRUD =====================

@app.route("/lists", methods=["POST"])
def create_list():
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM lists WHERE list_id = ?", (list_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        new_name = data.get("list_name", row["list_name"])
        conn.execute("UPDATE lists SET list_name = ? WHERE list_id = ?", (new_name, list_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"updated": list_id})


@app.route("/lists/<int:list_id>", methods=["DELETE"])
def delete_list(list_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT 1 FROM lists WHERE list_id = ?", (list_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        conn.execute("DELETE FROM list_accommodations WHERE list_id = ?", (list_id,))
        conn.execute("DELETE FROM lists WHERE list_id = ?", (list_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": list_id})


# ===================== LIST ACCOMMODATIONS CRUD =====================

@app.route("/lists/<int:list_id>/accommodations", methods=["POST"])
def add_to_list(list_id):
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM list_accommodations WHERE list_accom_id = ?", (list_accom_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        new_status = data.get("status", row["status"])
        new_room_id = data.get("room_id", row["room_id"])
        conn.execute(
            "UPDATE list_accommodations SET status = ?, room_id = ? WHERE list_accom_id = ?",
            (new_status, new_room_id, list_accom_id)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"updated": list_accom_id})


@app.route("/list-accommodations/<int:list_accom_id>", methods=["DELETE"])
def remove_from_list(list_accom_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT 1 FROM list_accommodations WHERE list_accom_id = ?", (list_accom_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        conn.execute("DELETE FROM list_accommodations WHERE list_accom_id = ?", (list_accom_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": list_accom_id})


# ===================== INTERNAL =====================

@app.route("/internal/accommodations-with-price", methods=["GET"])
def accommodations_with_price():
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT a.*, MIN(r.price_per_night) AS min_price
            FROM accommodations a
            LEFT JOIN room_types r ON r.accommodation_id = a.accommodation_id
            GROUP BY a.accommodation_id
        """).fetchall()
    finally:
        conn.close()

    results = []
    for r in rows:
        d = dict(r)
        d["facilities"] = safe_json_load(d.get("facilities"), [])
        d["min_price"] = d["min_price"] or 0
        results.append(d)
    return jsonify(results)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT)