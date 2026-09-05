import json
import sqlite3
import random

DATABASE_NAME = "plan.db"
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
# Premade Data
journeys_list = [
    (
        1,
        "Sydney Weekend",
        json.dumps(
            [
                "Bondi Beach",
                "Opera House",
                "Blue Mountains",
                "Harbour Bridge",
            ]
        ),
    ),
    (
        2,
        "Melbourne Foodie Trip",
        json.dumps(["Queen Victoria Market", "St Kilda", "Yarra Valley"]),
    ),
    (
        3,
        "Tropical North Queensland",
        json.dumps(
            [
                "Great Barrier Reef",
                "Daintree Rainforest",
                "Cape Tribulation",
                "Kuranda",
            ]
        ),
    ),
    (
        4,
        "Red Centre Adventure",
        json.dumps(["Uluru", "Kata Tjuta", "Kings Canyon", "Alice Springs"]),
    ),
    (
        5,
        "Tasmanian Wilderness",
        json.dumps(
            [
                "Cradle Mountain",
                "Freycinet National Park",
                "Mona Museum",
                "Port Arthur",
            ]
        ),
    ),
    (
        6,
        "Perth & Rottnest Island",
        json.dumps(
            [
                "Kings Park",
                "Cottesloe Beach",
                "Rottnest Island",
                "Fremantle Markets",
            ]
        ),
    ),
    (
        7,
        "Barossa Wine & Culture",
        json.dumps(
            [
                "Tanunda",
                "Barossa Valley Vineyards",
                "Adelaide Central Market",
                "Hahndorf",
            ]
        ),
    ),
    (
        8,
        "Great Ocean Road",
        json.dumps(
            ["Twelve Apostles", "Lorne", "Bells Beach", "Loch Ard Gorge"]
        ),
    ),
    (
        9,
        "Darwin & Top End",
        json.dumps(
            [
                "Kakadu National Park",
                "Litchfield National Park",
                "Mindil Beach",
                "Katherine Gorge",
            ]
        ),
    ),
    (
        10,
        "Ningaloo Reef Explorer",
        json.dumps(
            [
                "Exmouth",
                "Coral Bay",
                "Cape Range National Park",
                "Turquoise Bay",
            ]
        ),
    ),
]

trip_list = [
    (1, 1, 1, 5),
    # (2, 1, 2, 3),
    # (3, 1, 3, 2),
    # (4, 1, 4, 5),
    # (5, 1, 5, 8),
    # (6, 1, 6, 7),
    # (7, 1, 7, 3),
    # (8, 1, 8, 11),
    # (9, 1, 9, 8),
    # (10, 1, 10, 4),
]

days_list = []
trip_id = 1
duration = trip_list[0][3]
for i in range(duration):
    weather = random.choice(WEATHER_POOL)
    category = random.choice(list(ACTIVITY_CATEGORIES.keys()))
    itinerary_item = random.choice(ACTIVITY_CATEGORIES[category])
    
    # Structure: (trip_ID, weather, itinerary, activity)
    days_list.append((trip_id, weather, itinerary_item, category))


conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON")

# Create journey table
cursor.execute("""
CREATE TABLE IF NOT EXISTS journey (
    journey_ID INTEGER PRIMARY KEY,
    label TEXT NOT NULL,
    locations TEXT NOT NULL
)
""")

# Create trip table
cursor.execute("""
CREATE TABLE IF NOT EXISTS trip (
    trip_ID INTEGER PRIMARY KEY,
    user_ID INTEGER NOT NULL,
    journey_ID INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    FOREIGN KEY (journey_ID) REFERENCES journey(journey_ID)
)
""")

# Create day table
cursor.execute("""
CREATE TABLE IF NOT EXISTS day (
    day_ID INTEGER PRIMARY KEY,
    trip_ID INTEGER NOT NULL,
    weather TEXT,
    itinerary TEXT,
    activity TEXT,
    FOREIGN KEY (trip_ID) REFERENCES trip(trip_ID)
)
""")

# Reset existing data
cursor.execute("DELETE FROM day")
cursor.execute("DELETE FROM trip")
cursor.execute("DELETE FROM journey")

# Seed journeys
cursor.executemany(
    """
    INSERT INTO journey (journey_ID, label, locations)
    VALUES (?, ?, ?)
""",
    journeys_list,
)

# Seed trips
cursor.executemany(
    """
    INSERT INTO trip (trip_ID, user_ID, journey_ID, duration)
    VALUES (?, ?, ?, ?)
""",
    trip_list,
)

# Seed days
cursor.executemany(
    """
    INSERT INTO day (trip_ID, weather, itinerary, activity)
    VALUES (?, ?, ?, ?)
""",
    days_list,
)

conn.commit()
conn.close()

print("Database initialized with journeys, trips, and days.")