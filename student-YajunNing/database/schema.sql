CREATE TABLE IF NOT EXISTS flights (
    id INTEGER PRIMARY KEY,
    airline TEXT NOT NULL,
    flight_number TEXT NOT NULL UNIQUE,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    price_aud REAL NOT NULL CHECK (price_aud > 0),
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    stops INTEGER NOT NULL CHECK (stops >= 0)
);

CREATE TABLE IF NOT EXISTS saved_flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    flight_id INTEGER NOT NULL,
    departure_date TEXT NOT NULL,
    return_date TEXT,
    status TEXT NOT NULL DEFAULT 'considering'
        CHECK (status IN ('considering', 'booked', 'cancelled')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (flight_id) REFERENCES flights(id)
);

CREATE INDEX IF NOT EXISTS idx_saved_flights_username
ON saved_flights (username, updated_at DESC);
