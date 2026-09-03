"""Create the Flight SQLite database and insert the Release 0 seed catalogue."""

import sqlite3
from pathlib import Path


SEED_FLIGHTS = [
    (1, "Qantas", "QF25", "SYD", "HND", "20:50", "05:25", 890, 575, 0),
    (2, "Jetstar", "JQ11", "SYD", "NRT", "11:10", "19:20", 620, 610, 0),
    (3, "All Nippon Airways", "NH880", "SYD", "HND", "21:45", "05:30", 980, 585, 0),
    (4, "Japan Airlines", "JL52", "SYD", "HND", "09:15", "17:05", 940, 590, 0),
    (5, "Scoot", "TR3", "SYD", "NRT", "13:35", "08:00", 510, 865, 1),
    (6, "Cathay Pacific", "CX100", "SYD", "NRT", "14:00", "06:30", 730, 750, 1),
    (7, "Singapore Airlines", "SQ222", "SYD", "HND", "15:00", "06:15", 760, 855, 1),
    (8, "Philippine Airlines", "PR212", "SYD", "NRT", "11:30", "08:10", 580, 920, 1),
    (9, "AirAsia X", "D7218", "SYD", "NRT", "10:45", "08:25", 540, 880, 1),
    (10, "Fiji Airways", "FJ910", "SYD", "NRT", "13:15", "12:30", 690, 1035, 1),
]


def initialize_database(database_path):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).resolve().parent / "schema.sql"

    connection = sqlite3.connect(database_path)
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    connection.executemany(
        """
        INSERT OR IGNORE INTO flights (
            id, airline, flight_number, origin, destination,
            departure_time, arrival_time, price_aud, duration_minutes, stops
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        SEED_FLIGHTS,
    )
    connection.commit()
    connection.close()
