PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS places (
    attraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attraction_name TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    category TEXT NOT NULL,
    longitude REAL NOT NULL CHECK(longitude >= -180 AND longitude <= 180),
    latitude REAL NOT NULL CHECK(latitude >= -90 AND latitude <= 90),
    estimated_cost REAL NOT NULL DEFAULT 0 CHECK(estimated_cost >= 0),
    currency TEXT NOT NULL DEFAULT 'AUD' CHECK(length(currency) = 3),
    expected_duration_minutes INTEGER NOT NULL CHECK(expected_duration_minutes > 0),
    indoor_outdoor TEXT NOT NULL CHECK(indoor_outdoor IN ('indoor', 'outdoor', 'both')),
    crowd_level TEXT NOT NULL CHECK(crowd_level IN ('low', 'medium', 'high')),
    beginner_friendliness_score INTEGER NOT NULL CHECK(beginner_friendliness_score BETWEEN 1 AND 5),
    accessibility_information TEXT NOT NULL DEFAULT 'Not specified',
    attraction_description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendation_requests(
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id TEXT NOT NULL,
    destination_city TEXT NOT NULL,
    arrival_date DATE NOT NULL, 
    departure_date DATE NOT NULL,
    interests TEXT NOT NULL,
    weather_preferences TEXT NOT NULL,
    crowd_tolerance TEXT NOT NULL CHECK(crowd_tolerance IN ('low', 'medium', 'high')),
    budget_range TEXT NOT NULL CHECK(budget_range IN ('free','low', 'medium', 'high')),
    accessibility_needs TEXT NOT NULL DEFAULT 'None',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(arrival_date <= departure_date)
);

CREATE TABLE IF NOT EXISTS saved_places(
    saved_place_id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id TEXT NOT NULL,
    attraction_id INTEGER NOT NULL REFERENCES places(attraction_id) ON DELETE CASCADE,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (journey_id, attraction_id)  
);

CREATE INDEX IF NOT EXISTS index_places_city
    ON places(city);

CREATE INDEX IF NOT EXISTS index_places_category
    ON places(category);

CREATE INDEX IF NOT EXISTS index_recommendation_requests_journey
    ON recommendation_requests(journey_id);

CREATE INDEX IF NOT EXISTS index_saved_places_journey
    ON saved_places(journey_id);




