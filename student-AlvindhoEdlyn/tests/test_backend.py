import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# 1. Add backend directory to sys.path so app.py can be imported correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

# 2. Import app instance from app.py
from app import app


@pytest.fixture
def client():
    """Configures the Flask application test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# -------------------------------------------------------------------
# 1. Basic & Health Endpoints
# -------------------------------------------------------------------

def test_home_endpoint(client):
    """Test the root route."""
    response = client.get("/")
    assert response.status_code in [200, 500]


def test_health_endpoint(client):
    """Test health check route."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "student": "1"}


# -------------------------------------------------------------------
# 2. AI Context Route (/ask-with-context)
# -------------------------------------------------------------------

def test_ask_with_context_missing_question(client):
    """Test /ask-with-context with an empty question."""
    response = client.post("/ask-with-context", json={"question": ""})
    assert response.status_code == 400
    assert b"Question is required." in response.data


@patch("app.client.chat.completions.create")
def test_ask_with_context_success(mock_openai, client):
    """Test /ask-with-context with a valid query."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Mocked AI response."))
    ]
    mock_openai.return_value = mock_response

    payload = {"question": "What should I pack?", "itinerary": "Beach day"}
    response = client.post("/ask-with-context", json=payload)

    assert response.status_code == 200
    assert b"Mocked AI response." in response.data


# -------------------------------------------------------------------
# 3. Read Endpoints
# -------------------------------------------------------------------

@patch("app.requests.get")
def test_get_journeys(mock_get, client):
    """Test fetching journeys."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [{"journey_id": 1, "label": "Japan"}]

    response = client.get("/api/journeys")
    assert response.status_code == 200
    assert response.get_json() == [{"journey_id": 1, "label": "Japan"}]


@patch("app.requests.get")
def test_get_trips(mock_get, client):
    """Test fetching formatted trips."""
    def side_effect(url, **kwargs):
        mock_resp = MagicMock()
        if url.endswith("/api/trips"):
            mock_resp.status_code = 200
            mock_resp.json.return_value = [{"trip_ID": 1, "journey_ID": 10, "duration": 1}]
        elif url.endswith("/details"):
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"locations": ["Tokyo"]}
        elif url.endswith("/days"):
            mock_resp.status_code = 200
            mock_resp.json.return_value = [
                {"itinerary": "Tokyo Tour", "weather": "Sunny", "activity": "Sightseeing"}
            ]
        return mock_resp

    mock_get.side_effect = side_effect

    response = client.get("/api/trips")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["trip_id"] == 1


# -------------------------------------------------------------------
# 4. Trip Generation
# -------------------------------------------------------------------

def test_generate_trip_invalid_payload(client):
    """Test validation errors for generation endpoint."""
    response = client.post("/api/trips/generate", json={"duration": 0})
    assert response.status_code == 400


@patch("app.generate_ai_itinerary")
@patch("app.requests.post")
@patch("app.requests.get")
def test_generate_trip_success(mock_get, mock_post, mock_ai, client):
    """Test generating a trip."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"locations": ["Kyoto"], "label": "Kyoto Trip"}

    mock_ai.return_value = [
        {"summary": "Explore Temple", "activity": "Visit Shrine", "category": "Culture"}
    ]

    mock_post.return_value.status_code = 201
    mock_post.return_value.json.return_value = {
        "trip_id": 99,
        "days": [{
            "day_number": 1,
            "itinerary": "Explore Temple",
            "location": "Kyoto",
            "weather": "Sunny",
            "activity": "Visit Shrine"
        }]
    }

    payload = {"journeyId": 1, "duration": 1, "preferences": "Culture"}
    response = client.post("/api/trips/generate", json=payload)

    assert response.status_code == 201
    assert response.get_json()["trip_id"] == 99


# -------------------------------------------------------------------
# 5. Regeneration Endpoints
# -------------------------------------------------------------------

@patch("app.generate_ai_itinerary")
@patch("app.requests.put")
@patch("app.requests.get")
def test_regenerate_trip(mock_get, mock_put, mock_ai, client):
    """Test regenerating an entire trip."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "duration": 1,
        "locations": ["Osaka"],
        "user_id": 1,
        "journey_id": 2,
        "label": "Osaka Weekend"
    }

    mock_ai.return_value = [
        {"summary": "Osaka Castle", "activity": "Castle Tour", "category": "Sightseeing"}
    ]

    mock_put.return_value.status_code = 200
    mock_put.return_value.json.return_value = {"message": "Updated"}

    response = client.put("/api/trips/1/regenerate")
    assert response.status_code == 200
    assert response.get_json()["trip_id"] == 1


@patch("app.generate_ai_itinerary")
@patch("app.requests.put")
@patch("app.requests.get")
def test_regenerate_day(mock_get, mock_put, mock_ai, client):
    """Test regenerating a single day."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"locations": ["Nara"]}

    mock_ai.return_value = [
        {"summary": "Nara Park", "activity": "Feed Deer", "category": "Adventure"}
    ]

    mock_put.return_value.status_code = 200
    mock_put.return_value.json.return_value = {"message": "Day updated"}

    response = client.put("/api/trips/1/days/1")
    assert response.status_code == 200
    assert response.get_json()["day_number"] == 1


# -------------------------------------------------------------------
# 6. Delete Endpoints
# -------------------------------------------------------------------

@patch("app.requests.delete")
def test_delete_day(mock_delete, client):
    """Test deleting a single day."""
    mock_delete.return_value.status_code = 200
    mock_delete.return_value.json.return_value = {"message": "Day deleted"}

    response = client.delete("/api/trips/1/days/1")
    assert response.status_code == 200


@patch("app.requests.delete")
def test_delete_trip(mock_delete, client):
    """Test deleting a trip."""
    mock_delete.return_value.status_code = 200
    mock_delete.return_value.json.return_value = {"message": "Trip deleted"}

    response = client.delete("/api/trips/1")
    assert response.status_code == 200