import importlib.util
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
    "journey_id": "DATABASE-TEST-01",
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
    assert (
        read_response.get_json()["journey_id"]
        == "DATABASE-TEST-01"
    )

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
    saved_place = {
        "journey_id": "SAVED-TEST-01",
        "attraction_id": 1,
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

    read_response = client.get(
        f"/saved-places/{saved_place_id}"
    )

    assert read_response.status_code == 200
    assert (
        read_response.get_json()["journey_id"]
        == "SAVED-TEST-01"
    )

    saved_place["notes"] = "Visit in the afternoon"

    update_response = client.put(
        f"/saved-places/{saved_place_id}",
        json=saved_place
    )

    assert update_response.status_code == 200

    read_updated_response = client.get(
        f"/saved-places/{saved_place_id}"
    )

    assert (
        read_updated_response.get_json()["notes"]
        == "Visit in the afternoon"
    )

    delete_response = client.delete(
        f"/saved-places/{saved_place_id}"
    )

    assert delete_response.status_code == 200

    missing_response = client.get(
        f"/saved-places/{saved_place_id}"
    )

    assert missing_response.status_code == 404


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
        "/saved-places/999999"
    )

    assert missing_saved_place.status_code == 404