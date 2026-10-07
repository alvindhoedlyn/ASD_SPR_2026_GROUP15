import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Dynamically add the backend directory to sys.path using pathlib
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Import app instance from app.py
from app import app


@pytest.fixture
def client():
    """Configures the Flask application test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def mock_auth():
    """
    Every test gets a fake authenticated user (id=1) so protected routes
    (which call get_current_user_id()) don't 401. This mocks the real auth
    helper in app.py rather than disabling auth inside the app itself -
    app.py's actual auth/ownership logic stays untouched and is still what
    runs here, it's just fed a fake verified identity instead of calling
    out to shared-backend over the network.
    """
    with patch("app.get_current_user_id", return_value=(1, None)):
        yield


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
            # user_ID must match the mocked authenticated user (1) from
            # mock_auth - get_trips() filters to only the caller's own
            # trips, so a record missing/mismatching user_ID gets dropped
            # and the length assertion below would fail.
            mock_resp.json.return_value = [
                {"trip_ID": 1, "journey_ID": 10, "duration": 1, "user_ID": 1}
            ]
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
    # create_trip() only calls requests.get once (the journey lookup) - it
    # doesn't check ownership, since there's no existing trip to own yet.
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
    def side_effect(url, **kwargs):
        mock_resp = MagicMock()
        if url.endswith("/api/trips"):
            # get_trip_owner()'s ownership check - needs a LIST with this
            # trip owned by the mocked authenticated user (1), not the
            # flat dict the original test used (that shape only fits the
            # /details call below, and would raise a TypeError here since
            # the route code iterates it expecting trip records).
            mock_resp.status_code = 200
            mock_resp.json.return_value = [{"trip_ID": 1, "user_ID": 1}]
        elif url.endswith("/details"):
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "duration": 1,
                "locations": ["Osaka"],
                "user_id": 1,
                "journey_id": 2,
                "label": "Osaka Weekend"
            }
        return mock_resp

    mock_get.side_effect = side_effect

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
    def side_effect(url, **kwargs):
        mock_resp = MagicMock()
        if url.endswith("/api/trips"):
            # get_trip_owner()'s ownership check - same reasoning as above.
            mock_resp.status_code = 200
            mock_resp.json.return_value = [{"trip_ID": 1, "user_ID": 1}]
        elif url.endswith("/details"):
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"locations": ["Nara"]}
        return mock_resp

    mock_get.side_effect = side_effect

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

@patch("app.requests.get")
@patch("app.requests.delete")
def test_delete_day(mock_delete, mock_get, client):
    """Test deleting a single day."""
    # delete_day() now checks get_trip_owner() before deleting - without
    # mocking requests.get at all (as the original test didn't), that call
    # hits a real, unreachable DB_SERVICE_URL in CI, get_trip_owner()
    # catches the connection error and returns None, and the route 404s
    # as "Trip not found" instead of deleting.
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [{"trip_ID": 1, "user_ID": 1}]

    mock_delete.return_value.status_code = 200
    mock_delete.return_value.json.return_value = {"message": "Day deleted"}

    response = client.delete("/api/trips/1/days/1")
    assert response.status_code == 200


@patch("app.requests.get")
@patch("app.requests.delete")
def test_delete_trip(mock_delete, mock_get, client):
    """Test deleting a trip."""
    # Same reasoning as test_delete_day - delete_trip() also checks
    # get_trip_owner() first now.
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [{"trip_ID": 1, "user_ID": 1}]

    mock_delete.return_value.status_code = 200
    mock_delete.return_value.json.return_value = {"message": "Trip deleted"}

    response = client.delete("/api/trips/1")
    assert response.status_code == 200