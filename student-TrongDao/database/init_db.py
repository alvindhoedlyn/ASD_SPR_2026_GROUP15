import os
import sqlite3
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        BASE_DIR / "data" / "location_recommender.db"
    )
)

PLACES = [
    (
        "Sydney Opera House",
        "Sydney",
        "Australia",
        "landmark",
        151.2153,
        -33.8568,
        45.00,
        "AUD",
        120,
        "both",
        "high",
        5,
        "Wheelchair-accessible entrances and guided tours.",
        "Iconic harbour landmark offering tours, performances and harbour views."
    ),
    (
        "Royal Botanic Garden",
        "Sydney",
        "Australia",
        "nature",
        151.2167,
        -33.8642,
        0.00,
        "AUD",
        120,
        "outdoor",
        "medium",
        5,
        "Accessible paths and public facilities are available.",
        "Relaxed harbour-side gardens suitable for walking and picnics."
    ),
    (
        "The Rocks",
        "Sydney",
        "Australia",
        "history",
        151.2065,
        -33.8599,
        0.00,
        "AUD",
        120,
        "outdoor",
        "high",
        4,
        "Some historic areas contain uneven paths.",
        "Historic neighbourhood with markets, museums and harbour views."
    ),
    (
        "Art Gallery of New South Wales",
        "Sydney",
        "Australia",
        "art",
        151.2173,
        -33.8688,
        0.00,
        "AUD",
        120,
        "indoor",
        "low",
        5,
        "Wheelchair access, lifts and accessible facilities are available.",
        "Public art gallery with Australian, international and Indigenous collections."
    ),
    (
        "Darling Harbour",
        "Sydney",
        "Australia",
        "entertainment",
        151.1999,
        -33.8749,
        20.00,
        "AUD",
        180,
        "both",
        "high",
        4,
        "Mostly level pedestrian areas with accessible facilities.",
        "Waterfront precinct containing restaurants, museums and family attractions."
    ),
    (
        "SEA LIFE Sydney Aquarium",
        "Sydney",
        "Australia",
        "wildlife",
        151.2022,
        -33.8696,
        55.00,
        "AUD",
        120,
        "indoor",
        "high",
        5,
        "Wheelchair accessible with lifts throughout the attraction.",
        "Indoor aquarium featuring Australian marine animals and underwater exhibits."
    ),
    (
        "Taronga Zoo",
        "Sydney",
        "Australia",
        "wildlife",
        151.2411,
        -33.8430,
        51.00,
        "AUD",
        300,
        "outdoor",
        "medium",
        4,
        "Accessible paths are available, although some areas are steep.",
        "Harbour-side zoo with Australian and international wildlife."
    ),
    (
        "Bondi Beach",
        "Sydney",
        "Australia",
        "beach",
        151.2743,
        -33.8908,
        0.00,
        "AUD",
        180,
        "outdoor",
        "high",
        3,
        "Accessible promenade; beach access may be limited.",
        "Famous beach offering swimming, coastal walks and nearby dining."
    ),
    (
        "Manly Beach",
        "Sydney",
        "Australia",
        "beach",
        151.2875,
        -33.7963,
        10.00,
        "AUD",
        240,
        "outdoor",
        "medium",
        4,
        "Accessible ferry and mostly level beachfront promenade.",
        "Popular beach reached by ferry with swimming, shops and coastal walks."
    ),
    (
        "Barangaroo Reserve",
        "Sydney",
        "Australia",
        "nature",
        151.2016,
        -33.8572,
        0.00,
        "AUD",
        90,
        "outdoor",
        "low",
        5,
        "Wide accessible paths and nearby public facilities.",
        "Landscaped harbour reserve with walking paths and picnic areas."
    )
]


RECOMMENDATION_REQUESTS = [
    (
        "DEMO-01",
        "Sydney",
        "2026-09-01",
        "2026-09-05",
        "landmarks,history",
        "mild and dry",
        "medium",
        "low",
        "None",
        "completed"
    ),
    (
        "DEMO-02",
        "Sydney",
        "2026-09-02",
        "2026-09-06",
        "nature,walking",
        "sunny",
        "low",
        "free",
        "Wheelchair access",
        "completed"
    ),
    (
        "DEMO-03",
        "Sydney",
        "2026-09-03",
        "2026-09-07",
        "art,museums",
        "any",
        "low",
        "free",
        "Lift access",
        "completed"
    ),
    (
        "DEMO-04",
        "Sydney",
        "2026-09-04",
        "2026-09-08",
        "wildlife",
        "any",
        "high",
        "high",
        "None",
        "completed"
    ),
    (
        "DEMO-05",
        "Sydney",
        "2026-09-05",
        "2026-09-09",
        "beaches,swimming",
        "warm and sunny",
        "high",
        "free",
        "None",
        "completed"
    ),
    (
        "DEMO-06",
        "Sydney",
        "2026-09-06",
        "2026-09-10",
        "food,entertainment",
        "mild",
        "high",
        "medium",
        "Wheelchair access",
        "completed"
    ),
    (
        "DEMO-07",
        "Sydney",
        "2026-09-07",
        "2026-09-11",
        "photography,landmarks",
        "sunny",
        "medium",
        "low",
        "None",
        "completed"
    ),
    (
        "DEMO-08",
        "Sydney",
        "2026-09-08",
        "2026-09-12",
        "history,markets",
        "mild and dry",
        "medium",
        "free",
        "None",
        "completed"
    ),
    (
        "DEMO-09",
        "Sydney",
        "2026-09-09",
        "2026-09-13",
        "family,wildlife",
        "any",
        "medium",
        "high",
        "Wheelchair access",
        "completed"
    ),
    (
        "DEMO-10",
        "Sydney",
        "2026-09-10",
        "2026-09-14",
        "walking,nature",
        "mild",
        "low",
        "free",
        "Step-free access",
        "completed"
    )
]


SAVED_PLACE_NAMES = [
    ("DEMO-01", "Sydney Opera House"),
    ("DEMO-02", "Royal Botanic Garden"),
    ("DEMO-03", "Art Gallery of New South Wales"),
    ("DEMO-04", "SEA LIFE Sydney Aquarium"),
    ("DEMO-05", "Bondi Beach"),
    ("DEMO-06", "Darling Harbour"),
    ("DEMO-07", "Barangaroo Reserve"),
    ("DEMO-08", "The Rocks"),
    ("DEMO-09", "Taronga Zoo"),
    ("DEMO-10", "Manly Beach")
]


def create_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialise_database(reset=False):
    connection = create_connection()

    try:
        if reset:
            connection.executescript(
                """
                DROP TABLE IF EXISTS saved_places;
                DROP TABLE IF EXISTS recommendation_requests;
                DROP TABLE IF EXISTS places;
                """
            )

        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)

        places_count = connection.execute(
            "SELECT COUNT(*) FROM places"
        ).fetchone()[0]

        if places_count == 0:
            connection.executemany(
                """
                INSERT INTO places (
                    attraction_name,
                    city,
                    country,
                    category,
                    longitude,
                    latitude,
                    estimated_cost,
                    currency,
                    expected_duration_minutes,
                    indoor_outdoor,
                    crowd_level,
                    beginner_friendliness_score,
                    accessibility_information,
                    attraction_description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                PLACES
            )

        requests_count = connection.execute(
            "SELECT COUNT(*) FROM recommendation_requests"
        ).fetchone()[0]

        if requests_count == 0:
            connection.executemany(
                """
                INSERT INTO recommendation_requests (
                    journey_id,
                    destination_city,
                    arrival_date,
                    departure_date,
                    interests,
                    weather_preferences,
                    crowd_tolerance,
                    budget_range,
                    accessibility_needs,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                RECOMMENDATION_REQUESTS
            )

        saved_places_count = connection.execute(
            "SELECT COUNT(*) FROM saved_places"
        ).fetchone()[0]

        if saved_places_count == 0:
            place_ids = {
                row[1]: row[0]
                for row in connection.execute(
                    """
                    SELECT attraction_id, attraction_name
                    FROM places
                    """
                ).fetchall()
            }

            saved_places = [
                (
                    journey_id,
                    place_ids[attraction_name],
                    "Seeded demonstration favourite"
                )
                for journey_id, attraction_name in SAVED_PLACE_NAMES
            ]

            connection.executemany(
                """
                INSERT INTO saved_places (
                    journey_id,
                    attraction_id,
                    notes
                )
                VALUES (?, ?, ?)
                """,
                saved_places
            )

        connection.commit()

        print(f"Database ready: {DATABASE_PATH}")

        for table_name in (
            "places",
            "recommendation_requests",
            "saved_places"
        ):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]

            print(f"{table_name}: {count} records")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    initialise_database(reset="--reset" in sys.argv)