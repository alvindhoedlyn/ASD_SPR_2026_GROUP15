CREATE TABLE IF NOT EXISTS accommodations (
    accommodation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city_area TEXT NOT NULL,
    description TEXT,
    facilities TEXT,
    images TEXT,
    avg_rating REAL DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS room_types (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    accommodation_id INTEGER NOT NULL,
    room_name TEXT,
    price_per_night REAL NOT NULL,
    available_rooms INTEGER DEFAULT 1,
    capacity INTEGER DEFAULT 2,
    images TEXT,
    FOREIGN KEY (accommodation_id) REFERENCES accommodations(accommodation_id)
);

CREATE TABLE IF NOT EXISTS priorities (
    priority_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    price_weight REAL DEFAULT 50,
    location_weight REAL DEFAULT 50,
    facility_weight REAL DEFAULT 50,
    review_weight REAL DEFAULT 50,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lists (
    list_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    list_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS list_accommodations (
    list_accom_id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER NOT NULL,
    accommodation_id INTEGER NOT NULL,
    room_id INTEGER,
    status TEXT DEFAULT 'Option' CHECK (status IN ('Option', 'Rejected', 'Accepted')),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (list_id) REFERENCES lists(list_id),
    FOREIGN KEY (accommodation_id) REFERENCES accommodations(accommodation_id),
    FOREIGN KEY (room_id) REFERENCES room_types(room_id)
);