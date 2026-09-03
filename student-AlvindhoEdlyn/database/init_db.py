import sqlite3

DATABASE_NAME = "plan.db"

#Premade Data
trip_list = [
    (1, 1, 5),
    (2, 1, 3),
    (3, 1, 2),
    (4, 1, 5),
    (5, 1, 8),
    (6, 1, 7),
    (7, 1, 3),
    (8, 1, 11),
    (9, 1, 8),
    (10, 1, 4),

]
days_list = [
    (1, "Sunny", "City tour", "Sightseeing"),
    (1, "Rainy", "Museum visit", "Indoor activities"),
    (1, "Cloudy", "Beach walk", "Relaxing"),
    (1, "Sunny", "Hiking trail", "Hiking"),
    (1, "Windy", "Harbor tour", "Boat ride"),
    (1, "Sunny", "Old town", "Walking tour"),
    (1, "Rainy", "Shopping district", "Shopping"),
    (1, "Cloudy", "National park", "Wildlife watching"),
    (1, "Sunny", "Local market", "Food tasting"),
    (1, "Clear", "Sunset viewpoint", "Photography"),
]


conn = sqlite3.connect(DATABASE_NAME)
with open("schema.sql") as f:
    conn.executescript(f.read())
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON")

cursor.execute("""
CREATE TABLE IF NOT EXISTS trip (
    trip_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    user_ID INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    FOREIGN KEY (user_ID) REFERENCES USER(user_ID)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS day (
    day_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_ID INTEGER NOT NULL,
    weather TEXT,
    itinerary TEXT,
    activity TEXT,
    FOREIGN KEY (trip_ID) REFERENCES trip(trip_ID)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS loc_list (
    day_ID INTEGER NOT NULL,
    location_ID INTEGER NOT NULL,
    PRIMARY KEY (day_ID, location_ID),
    FOREIGN KEY (day_ID) REFERENCES DAY(day_ID),
    FOREIGN KEY (location_ID) REFERENCES LOCATION(location_ID)
)
""")

cursor.execute("DELETE FROM loc_list")
cursor.execute("DELETE FROM day")
cursor.execute("DELETE FROM trip")

cursor.execute(
    "INSERT INTO trip (trip_id, user_id, duration) VALUES (1, 1, 10)",
)
cursor.executemany("""
    INSERT INTO DAY (trip_ID, weather, itinerary, activity)
    VALUES (?, ?, ?, ?)
""", days_list)

conn.commit()
conn.close()

print("Database initialized with one trip and 10 days.")