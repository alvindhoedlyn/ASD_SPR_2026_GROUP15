CREATE TABLE IF NOT EXISTS trip (
    trip_ID INTEGER PRIMARY KEY,
    user_ID INTEGER NOT NULL,
    journey_ID INTEGER NOT NULL,
    duration INTEGER NOT NULL,
);

CREATE TABLE IF NOT EXISTS day(
    day_ID INTEGER PRIMARY KEY,
    trip_ID INTEGER NOT NULL,
    weather TEXT,
    itinerary TEXT,
    activity TEXT,
    FOREIGN KEY (trip_ID) REFERENCES trip(trip_ID)
);