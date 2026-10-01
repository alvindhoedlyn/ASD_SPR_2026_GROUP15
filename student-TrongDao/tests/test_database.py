import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest


DATABASE_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "database"
)

DATABASE_APP_PATH = DATABASE_DIRECTORY / "app.py"


PLACE_DATA = {
    "attraction_name": "Test Harbour Museum",
    "city": "Sydney",
    "country": "Australia",
    "category": "history",
    "longitude": 151.2,
    "latitude": -33.8,
    "estimated_cost": 20,
    "currency": "AUD",
    "expected_duration_minutes": 90,
    "indoor_outdoor": "indoor",
    "crowd_level": "low",
    "beginner_friendliness_score": 5,
    "accessibility_information": "Wheelchair accessible",
    "attraction_description": "A test attraction."
}


REQUEST_DATA = {
    "destination_city": "Sydney",
    "arrival_date": "2026-09-10",
    "departure_date": "2026-09-15",
    "interests": "history,nature",
    "weather_preferences": "both",
    "crowd_tolerance": "medium",
    "budget_range": "low",
    "accessibility_needs": "None",
    "status": "completed"
}


def test_saved_place_migration_adds_account_ownership():
    specification = importlib.util.spec_from_file_location(
        "location_init_db_migration_test",
        DATABASE_DIRECTORY / "init_db.py"
    )
    init_db = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(init_db)

    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE places(attraction_id INTEGER PRIMARY KEY)"
    )
    connection.execute("INSERT INTO places VALUES (10)")
    connection.execute(
        """
        CREATE TABLE saved_places(
            saved_place_id INTEGER PRIMARY KEY AUTOINCREMENT,
            attraction_id INTEGER NOT NULL UNIQUE,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO saved_places(attraction_id, notes)
        VALUES (10, 'Preserved note')
        """
    )

    init_db.migrate_saved_places(connection)

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(saved_places)"
        ).fetchall()
    }
    migrated_record = connection.execute(
        """
        SELECT saved_place_id, user_id, attraction_id, notes
        FROM saved_places
        """
    ).fetchone()

    assert "journey_id" not in columns
    assert "user_id" in columns
    assert migrated_record == (1, 1, 10, "Preserved note")

    connection.execute(
        """
        INSERT INTO saved_places(user_id, attraction_id, notes)
        VALUES (2, 10, 'Another account')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO saved_places(user_id, attraction_id, notes)
            VALUES (1, 10, 'Duplicate for same account')
            """
        )

    connection.close()


def test_recommendation_request_migration_removes_journey_id():
    specification = importlib.util.spec_from_file_location(
        "location_init_db_recommendation_migration_test",
        DATABASE_DIRECTORY / "init_db.py"
    )
    init_db = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(init_db)

    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE recommendation_requests(
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            journey_id TEXT NOT NULL,
            destination_city TEXT NOT NULL,
            arrival_date DATE NOT NULL,
            departure_date DATE NOT NULL,
            interests TEXT NOT NULL,
            weather_preferences TEXT NOT NULL,
            crowd_tolerance TEXT NOT NULL,
            budget_range TEXT NOT NULL,
            accessibility_needs TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
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
        (
            "LEGACY-01",
            "Sydney",
            "2026-09-10",
            "2026-09-15",
            "nature",
            "outdoor",
            "medium",
            "low",
            "None",
            "completed"
        )
    )

    init_db.migrate_recommendation_requests(connection)

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(recommendation_requests)"
        ).fetchall()
    }
    migrated_record = connection.execute(
        """
        SELECT request_id, destination_city, status
        FROM recommendation_requests
        """
    ).fetchone()

    assert "journey_id" not in columns
    assert migrated_record == (1, "Sydney", "completed")

    connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_database = tmp_path / "location_test.db"

    monkeypatch.setenv(
        "DATABASE_PATH",
        str(test_database)
    )

    sys.modules.pop("init_db", None)
    sys.path.insert(0, str(DATABASE_DIRECTORY))

    module_name = (
        f"location_database_app_{tmp_path.name}"
    )

    specification = (
        importlib.util.spec_from_file_location(
            module_name,
            DATABASE_APP_PATH
        )
    )

    database_app = (
        importlib.util.module_from_spec(specification)
    )

    specification.loader.exec_module(database_app)

    database_app.app.config["TESTING"] = True

    with database_app.app.test_client() as test_client:
        yield test_client

    sys.path.remove(str(DATABASE_DIRECTORY))


def test_health_endpoint(client):
    response = client.get("/health")
    response_data = response.get_json()

    assert response.status_code == 200
    assert response_data["status"] == "running"
    assert response_data["service"] == (
        "location-recommender-database"
    )


def test_place_crud(client):
    create_response = client.post(
        "/places",
        json=PLACE_DATA
    )

    assert create_response.status_code == 201

    attraction_id = (
        create_response.get_json()["attraction_id"]
    )

    read_response = client.get(
        f"/places/{attraction_id}"
    )

    assert read_response.status_code == 200
    assert (
        read_response.get_json()["attraction_name"]
        == "Test Harbour Museum"
    )

    updated_place = PLACE_DATA.copy()
    updated_place["attraction_name"] = (
        "Updated Harbour Museum"
    )
    updated_place["estimated_cost"] = 25

    update_response = client.put(
        f"/places/{attraction_id}",
        json=updated_place
    )

    assert update_response.status_code == 200

    read_updated_response = client.get(
        f"/places/{attraction_id}"
    )

    assert (
        read_updated_response.get_json()[
            "attraction_name"
        ]
        == "Updated Harbour Museum"
    )

    delete_response = client.delete(
        f"/places/{attraction_id}"
    )

    assert delete_response.status_code == 200

    missing_response = client.get(
        f"/places/{attraction_id}"
    )

    assert missing_response.status_code == 404


def test_recommendation_request_crud(client):
    create_response = client.post(
        "/recommendation-requests",
        json=REQUEST_DATA
    )

    assert create_response.status_code == 201

    request_id = (
        create_response.get_json()["request_id"]
    )

    read_response = client.get(
        f"/recommendation-requests/{request_id}"
    )

    assert read_response.status_code == 200
    assert "journey_id" not in read_response.get_json()

    updated_request = REQUEST_DATA.copy()
    updated_request["status"] = "failed"

    update_response = client.put(
        f"/recommendation-requests/{request_id}",
        json=updated_request
    )

    assert update_response.status_code == 200

    read_updated_response = client.get(
        f"/recommendation-requests/{request_id}"
    )

    assert (
        read_updated_response.get_json()["status"]
        == "failed"
    )

    delete_response = client.delete(
        f"/recommendation-requests/{request_id}"
    )

    assert delete_response.status_code == 200

    missing_response = client.get(
        f"/recommendation-requests/{request_id}"
    )

    assert missing_response.status_code == 404


def test_saved_place_crud(client):
    place_response = client.post(
        "/places",
        json=PLACE_DATA
    )

    assert place_response.status_code == 201

    saved_place = {
        "user_id": 1,
        "attraction_id": place_response.get_json()["attraction_id"],
        "notes": "Visit in the morning"
    }

    create_response = client.post(
        "/saved-places",
        json=saved_place
    )

    assert create_response.status_code == 201

    saved_place_id = (
        create_response.get_json()["saved_place_id"]
    )

    duplicate_response = client.post(
        "/saved-places",
        json=saved_place
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.get_json()["error"] == (
        "This attraction is already saved"
    )

    read_response = client.get(
        f"/saved-places/{saved_place_id}?user_id=1"
    )

    assert read_response.status_code == 200
    assert read_response.get_json()["saved_place_id"] == saved_place_id
    assert "journey_id" not in read_response.get_json()

    saved_place["notes"] = "Visit in the afternoon"

    update_response = client.put(
        f"/saved-places/{saved_place_id}",
        json=saved_place
    )

    assert update_response.status_code == 200

    read_updated_response = client.get(
        f"/saved-places/{saved_place_id}?user_id=1"
    )

    assert (
        read_updated_response.get_json()["notes"]
        == "Visit in the afternoon"
    )

    delete_response = client.delete(
        f"/saved-places/{saved_place_id}?user_id=1"
    )

    assert delete_response.status_code == 200

    missing_response = client.get(
        f"/saved-places/{saved_place_id}?user_id=1"
    )

    assert missing_response.status_code == 404


def test_saved_places_are_isolated_by_user(client):
    place_response = client.post("/places", json=PLACE_DATA)
    attraction_id = place_response.get_json()["attraction_id"]

    first_user_response = client.post(
        "/saved-places",
        json={
            "user_id": 1,
            "attraction_id": attraction_id,
            "notes": "First user's note"
        }
    )
    second_user_response = client.post(
        "/saved-places",
        json={
            "user_id": 2,
            "attraction_id": attraction_id,
            "notes": "Second user's note"
        }
    )

    assert first_user_response.status_code == 201
    assert second_user_response.status_code == 201

    first_saved_place_id = first_user_response.get_json()[
        "saved_place_id"
    ]

    first_user_list = client.get("/saved-places?user_id=1")
    second_user_list = client.get("/saved-places?user_id=2")

    first_user_matches = [
        place for place in first_user_list.get_json()
        if place["attraction_id"] == attraction_id
    ]
    second_user_matches = [
        place for place in second_user_list.get_json()
        if place["attraction_id"] == attraction_id
    ]

    assert [place["notes"] for place in first_user_matches] == [
        "First user's note"
    ]
    assert [place["notes"] for place in second_user_matches] == [
        "Second user's note"
    ]

    cross_account_read = client.get(
        f"/saved-places/{first_saved_place_id}?user_id=2"
    )
    cross_account_update = client.put(
        f"/saved-places/{first_saved_place_id}",
        json={"user_id": 2, "notes": "Changed by user 2"}
    )
    cross_account_delete = client.delete(
        f"/saved-places/{first_saved_place_id}?user_id=2"
    )

    assert cross_account_read.status_code == 404
    assert cross_account_update.status_code == 404
    assert cross_account_delete.status_code == 404

    owner_read = client.get(
        f"/saved-places/{first_saved_place_id}?user_id=1"
    )
    assert owner_read.status_code == 200
    assert owner_read.get_json()["notes"] == "First user's note"


def test_invalid_requests(client):
    missing_place_fields = client.post(
        "/places",
        json={}
    )

    assert missing_place_fields.status_code == 400
    assert (
        missing_place_fields.get_json()["error"]
        == "Missing required fields"
    )

    missing_place = client.get("/places/999999")

    assert missing_place.status_code == 404

    missing_saved_place = client.get(
        "/saved-places/999999?user_id=1"
    )

    assert missing_saved_place.status_code == 404
