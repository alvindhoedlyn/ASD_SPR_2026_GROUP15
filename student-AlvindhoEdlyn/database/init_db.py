from flask import Flask, request, jsonify
import sqlite3
import random
import json
import os

app = Flask(__name__)

# Ensure the directory path exists before creating plan.db
DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/plan.db")
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

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

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates tables and seeds default data on app startup."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS journey (
        journey_ID INTEGER PRIMARY KEY,
        label TEXT NOT NULL,
        locations TEXT NOT NULL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trip (
        trip_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        user_ID INTEGER NOT NULL,
        journey_ID INTEGER NOT NULL,
        duration INTEGER NOT NULL,
        FOREIGN KEY (journey_ID) REFERENCES journey(journey_ID)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS day (
        day_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_ID INTEGER NOT NULL,
        weather TEXT,
        itinerary TEXT,
        activity TEXT,
        FOREIGN KEY (trip_ID) REFERENCES trip(trip_ID)
    )""")

    # Seed Journeys if empty
    cursor.execute("SELECT COUNT(*) FROM journey")
    if cursor.fetchone()[0] == 0:
        journeys_list = [
            (1, "Sydney Weekend", json.dumps(["Bondi Beach", "Opera House", "Blue Mountains", "Harbour Bridge"])),
            (2, "Melbourne Foodie Trip", json.dumps(["Queen Victoria Market", "St Kilda", "Yarra Valley"])),
            (3, "Tropical North Queensland", json.dumps(["Great Barrier Reef", "Daintree Rainforest", "Cape Tribulation", "Kuranda"])),
            (4, "Red Centre Adventure", json.dumps(["Uluru", "Kata Tjuta", "Kings Canyon", "Alice Springs"])),
            (5, "Tasmanian Wilderness", json.dumps(["Cradle Mountain", "Freycinet National Park", "Mona Museum", "Port Arthur"])),
            (6, "Perth & Rottnest Island", json.dumps(["Kings Park", "Cottesloe Beach", "Rottnest Island", "Fremantle Markets"])),
            (7, "Barossa Wine & Culture", json.dumps(["Tanunda", "Barossa Valley Vineyards", "Adelaide Central Market", "Hahndorf"])),
            (8, "Great Ocean Road", json.dumps(["Twelve Apostles", "Lorne", "Bells Beach", "Loch Ard Gorge"])),
            (9, "Darwin & Top End", json.dumps(["Kakadu National Park", "Litchfield National Park", "Mindil Beach", "Katherine Gorge"])),
            (10, "Ningaloo Reef Explorer", json.dumps(["Exmouth", "Coral Bay", "Cape Range National Park", "Turquoise Bay"]))
        ]
        cursor.executemany("INSERT INTO journey (journey_ID, label, locations) VALUES (?, ?, ?)", journeys_list)
        
        # Seed default trip and days
        cursor.execute("INSERT INTO trip (user_ID, journey_ID, duration) VALUES (1, 1, 5)")
        trip_id = cursor.lastrowid

        days_list = []
        for _ in range(5):
            weather = random.choice(WEATHER_POOL)
            category = random.choice(list(ACTIVITY_CATEGORIES.keys()))
            itinerary_item = random.choice(ACTIVITY_CATEGORIES[category])
            days_list.append((trip_id, weather, itinerary_item, category))

        cursor.executemany("INSERT INTO day (trip_ID, weather, itinerary, activity) VALUES (?, ?, ?, ?)", days_list)

    conn.commit()
    conn.close()

# Initialize DB when backend starts
init_db()

# ----- API ENDPOINTS -----

@app.route("/api/journeys", methods=["GET"])
def get_journeys():
    conn = get_db()
    journeys = conn.execute("SELECT * FROM journey").fetchall()
    conn.close()
    return jsonify([
        {"journey_id": j["journey_ID"], "label": j["label"], "locations": json.loads(j["locations"])}
        for j in journeys
    ])

@app.route("/api/trips", methods=["GET"])
def get_trips():
    conn = get_db()
    trips = conn.execute("SELECT * FROM trip ORDER BY trip_ID ASC").fetchall()
    conn.close()
    return jsonify([dict(t) for t in trips])

@app.route("/api/trips/<int:trip_id>/details", methods=["GET"])
def get_trip_details(trip_id):
    conn = get_db()
    data = conn.execute("""
        SELECT t.trip_ID, j.locations 
        FROM trip t
        JOIN journey j ON t.journey_ID = j.journey_ID
        WHERE t.trip_ID = ?
    """, (trip_id,)).fetchone()
    conn.close()
    
    if not data:
        return jsonify({"error": "Trip not found"}), 404
        
    return jsonify({"locations": json.loads(data["locations"])})

@app.route("/api/trips/<int:trip_id>/days", methods=["GET"])
def get_trip_days(trip_id):
    conn = get_db()
    days = conn.execute("SELECT * FROM day WHERE trip_ID = ? ORDER BY day_ID ASC", (trip_id,)).fetchall()
    conn.close()
    return jsonify([dict(d) for d in days])

@app.route("/api/journeys/<int:journey_id>", methods=["GET"])
def get_journey_by_id(journey_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM journey WHERE journey_ID = ?", (journey_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Journey not found"}), 404

    return jsonify({
        "journey_id": row["journey_ID"],
        "label": row["label"],
        "locations": json.loads(row["locations"])
    }), 200


@app.route("/api/trips", methods=["POST"])
def create_trip():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    journey_id = data.get("journey_id")
    duration = data.get("duration")
    days = data.get("days", [])

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO trip (user_ID, journey_ID, duration) VALUES (?, ?, ?)",
            (user_id, journey_id, duration)
        )
        new_trip_id = cursor.lastrowid

        created_days = []
        for d in days:
            cursor.execute(
                """
                INSERT INTO day (trip_ID, weather, itinerary, activity)
                VALUES (?, ?, ?, ?)
                """,
                (new_trip_id, d["weather"], d["itinerary"], d["activity"])
            )
            created_days.append({
                "day_id": cursor.lastrowid,
                "day_number": d["day_number"],
                "location": d["location"],
                "weather": d["weather"],
                "itinerary": d["itinerary"],
                "activity": d["activity"]
            })

        conn.commit()
        conn.close()

        return jsonify({
            "trip_id": new_trip_id,
            "days": created_days
        }), 201

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["PUT"])
def update_trip_day(trip_id, day_number):
    data = request.get_json() or {}
    new_weather = data.get("weather")
    new_itinerary = data.get("itinerary")
    new_activity = data.get("activity")

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Target specific day row using 0-based offset matching day_number
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

        # Execute database UPDATE
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

        return jsonify({"message": "Day updated successfully"}), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/trips/<int:trip_id>/days/<int:day_number>", methods=["DELETE"])
def delete_trip_day(trip_id, day_number):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Locate day record by zero-indexed offset matching day_number
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

        # Delete target day and decrement trip duration counter
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
def delete_trip_record(trip_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Delete dependent day entries first
        cursor.execute("DELETE FROM day WHERE trip_ID = ?", (trip_id,))
        # Delete parent trip entry
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
    port = int(os.getenv("PORT", 6001))
    app.run(host="0.0.0.0", port=port)