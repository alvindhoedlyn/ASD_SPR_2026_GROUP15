import sys
import os
import pytest
import tempfile
from unittest.mock import patch

# 1. Add project root & database directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "database")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def client(tmp_path):
    """Creates a temporary SQLite DB file and initializes the Flask test client."""
    db_file = tmp_path / "test_plan.db"

    # Patch DATABASE_PATH in init_db before importing/running init_db
    with patch("init_db.DATABASE_PATH", str(db_file)):
        import init_db
        init_db.init_db()  # Initialize schema and seed data in temp DB
        
        init_db.app.config["TESTING"] = True
        with init_db.app.test_client() as client:
            yield client


# -------------------------------------------------------------------
# 1. GET Journeys & Trips Tests
# -------------------------------------------------------------------

def test_get_journeys(client):
    """Test fetching initial seeded journeys."""
    response = client.get("/api/journeys")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 10
    assert data[0]["label"] == "Sydney Weekend"


def test_get_journey_by_id_success(client):
    """Test fetching a valid journey by ID."""
    response = client.get("/api/journeys/1")
    assert response.status_code == 200
    data = response.get_json()
    assert data["journey_id"] == 1
    assert data["label"] == "Sydney Weekend"


def test_get_journey_by_id_not_found(client):
    """Test fetching a non-existent journey ID."""
    response = client.get("/api/journeys/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Journey not found"}


def test_get_trips(client):
    """Test fetching initial seeded trips."""
    response = client.get("/api/trips")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1


def test_get_trip_details_success(client):
    """Test fetching trip details for existing trip."""
    response = client.get("/api/trips/1/details")
    assert response.status_code == 200
    data = response.get_json()
    assert "locations" in data


def test_get_trip_details_not_found(client):
    """Test fetching trip details for non-existent trip."""
    response = client.get("/api/trips/999/details")
    assert response.status_code == 404


def test_get_trip_days(client):
    """Test fetching days for trip 1."""
    response = client.get("/api/trips/1/days")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 5


# -------------------------------------------------------------------
# 2. POST (Create) Trip Test
# -------------------------------------------------------------------

def test_create_trip_success(client):
    """Test creating a new trip with days."""
    payload = {
        "user_id": 2,
        "journey_id": 2,
        "duration": 2,
        "days": [
            {
                "day_number": 1,
                "location": "St Kilda",
                "weather": "Sunny",
                "itinerary": "Cafe hopping",
                "activity": "Food & Drink"
            },
            {
                "day_number": 2,
                "location": "Yarra Valley",
                "weather": "Clear",
                "itinerary": "Wine tasting",
                "activity": "Relaxation"
            }
        ]
    }
    response = client.post("/api/trips", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert "trip_id" in data
    assert len(data["days"]) == 2


# -------------------------------------------------------------------
# 3. PUT (Update/Overwrite) Trip & Days Tests
# -------------------------------------------------------------------

def test_update_full_trip(client):
    """Test completely overwriting trip 1."""
    payload = {
        "days": [
            {
                "day_number": 1,
                "location": "Bondi Beach",
                "weather": "Windy",
                "itinerary": "Surfing lesson",
                "activity": "Adventure"
            }
        ]
    }
    response = client.put("/api/trips/1", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["trip_id"] == 1
    assert len(data["days"]) == 1


def test_update_trip_day(client):
    """Test updating day 1 of trip 1."""
    payload = {
        "weather": "Thunderstorms",
        "itinerary": "Indoor Museum Visit",
        "activity": "Culture"
    }
    response = client.put("/api/trips/1/days/1", json=payload)
    assert response.status_code == 200
    assert response.get_json()["message"] == "Day updated successfully"


def test_update_trip_day_not_found(client):
    """Test updating a non-existent day offset."""
    response = client.put("/api/trips/1/days/99", json={"weather": "Sunny"})
    assert response.status_code == 404


# -------------------------------------------------------------------
# 4. DELETE Trip & Days Tests
# -------------------------------------------------------------------

def test_delete_trip_day(client):
    """Test deleting day 1 from trip 1."""
    response = client.delete("/api/trips/1/days/1")
    assert response.status_code == 200
    assert response.get_json()["message"] == "Day deleted successfully"


def test_delete_trip_record(client):
    """Test deleting trip 1 and its cascading days."""
    response = client.delete("/api/trips/1")
    assert response.status_code == 200
    assert response.get_json()["message"] == "Trip deleted successfully"

    # Confirm deletion
    get_res = client.get("/api/trips/1/details")
    assert get_res.status_code == 404