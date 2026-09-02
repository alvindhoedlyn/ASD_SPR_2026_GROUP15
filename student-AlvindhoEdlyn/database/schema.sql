CREATE TABLE IF NOT EXISTS trip (
    trip_ID INTEGER PRIMARY KEY,
    user_ID INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    FOREIGN KEY (user_ID) REFERENCES user(user_ID)
);

CREATE TABLE IF NOT EXISTS day AUTOINCREMENT(
    day_ID INTEGER PRIMARY KEY,
    trip_ID INTEGER NOT NULL,
    weather TEXT,
    itinerary TEXT,
    activity TEXT,
    FOREIGN KEY (trip_ID) REFERENCES trip(trip_ID)
);

CREATE TABLE IF NOT EXISTS loc_list (
    day_ID INTEGER NOT NULL,
    location_ID INTEGER NOT NULL,
    PRIMARY KEY (day_ID, location_ID),
    FOREIGN KEY (day_ID) REFERENCES day(day_ID),
    FOREIGN KEY (location_ID) REFERENCES loc(location_ID)
);
