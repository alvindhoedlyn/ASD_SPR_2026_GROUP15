"""
Tests for the Accommodation Recommender database microservice.

Run with:
    pytest student-RenzoRobin/tests/test_database.py -v

Each test gets a fresh, empty SQLite file so tests don't interfere
with each other and never touch the real accommodation.db.
"""
import importlib.util
import json
import os
import tempfile

import pytest

_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "app.py")


def _load_db_app():
    # Loaded under a unique module name (not "app") so it can't collide
    # with the backend service's own app.py in the same pytest session.
    spec = importlib.util.spec_from_file_location("renzorobin_database_app", _APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["DATABASE_PATH"] = db_path

    db_app = _load_db_app()
    db_app.init_db()
    db_app.app.config["TESTING"] = True

    with db_app.app.test_client() as test_client:
        yield test_client

    os.close(db_fd)
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(db_path + suffix)
        except FileNotFoundError:
            pass


def create_accommodation(client, **overrides):
    payload = {
        "name": "Test Villa",
        "city_area": "Testville",
        "description": "A place for tests",
        "facilities": ["wifi", "pool"],
        "images": [],
        "avg_rating": 4.5,
        "review_count": 10,
    }
    payload.update(overrides)
    resp = client.post("/accommodations", json=payload)
    return resp


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


class TestSeedData:
    def test_seed_data_is_loaded_on_init(self, client):
        resp = client.get("/accommodations")
        assert resp.status_code == 200
        listings = resp.get_json()
        assert len(listings) == 30
        names = {l["name"] for l in listings}
        assert "Ubud Riverside Villa" in names

    def test_areas_returns_distinct_cities_sorted(self, client):
        resp = client.get("/areas")
        assert resp.status_code == 200
        areas = resp.get_json()
        assert areas == sorted(areas)
        assert "Bali, Indonesia" in areas


class TestAccommodationCRUD:
    def test_create_accommodation(self, client):
        resp = create_accommodation(client)
        assert resp.status_code == 201
        assert "accommodation_id" in resp.get_json()

    def test_get_accommodation_deserializes_json_fields(self, client):
        created = create_accommodation(client, facilities=["wifi", "parking"]).get_json()
        resp = client.get(f"/accommodations/{created['accommodation_id']}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["facilities"] == ["wifi", "parking"]
        assert isinstance(body["images"], list)

    def test_get_nonexistent_accommodation_returns_404(self, client):
        resp = client.get("/accommodations/99999")
        assert resp.status_code == 404

    def test_update_accommodation(self, client):
        created = create_accommodation(client).get_json()
        resp = client.put(
            f"/accommodations/{created['accommodation_id']}",
            json={
                "name": "Updated Villa",
                "city_area": "Testville",
                "description": "Updated",
                "facilities": ["wifi"],
                "images": [],
                "avg_rating": 5.0,
                "review_count": 20,
            },
        )
        assert resp.status_code == 200
        fetched = client.get(f"/accommodations/{created['accommodation_id']}").get_json()
        assert fetched["name"] == "Updated Villa"
        assert fetched["avg_rating"] == 5.0

    def test_delete_accommodation_cascades_rooms(self, client):
        created = create_accommodation(client).get_json()
        accom_id = created["accommodation_id"]
        client.post(f"/accommodations/{accom_id}/rooms", json={
            "room_name": "Standard", "price_per_night": 50, "available_rooms": 2, "capacity": 2,
        })

        resp = client.delete(f"/accommodations/{accom_id}")
        assert resp.status_code == 200

        assert client.get(f"/accommodations/{accom_id}").status_code == 404
        assert client.get(f"/accommodations/{accom_id}/rooms").get_json() == []

    def test_filter_accommodations_by_city(self, client):
        resp = client.get("/accommodations?city=Kyoto")
        results = resp.get_json()
        assert len(results) == 10
        assert all(r["city_area"] == "Kyoto, Japan" for r in results)

    def test_filter_accommodations_by_facility(self, client):
        resp = client.get("/accommodations?facility=parking")
        results = resp.get_json()
        assert all("parking" in r["facilities"] for r in results)
        assert len(results) >= 1


class TestRoomTypeCRUD:
    def test_create_and_list_rooms(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        resp = client.post(f"/accommodations/{accom_id}/rooms", json={
            "room_name": "Deluxe", "price_per_night": 120, "available_rooms": 1, "capacity": 3,
        })
        assert resp.status_code == 201

        rooms = client.get(f"/accommodations/{accom_id}/rooms").get_json()
        assert len(rooms) == 1
        assert rooms[0]["room_name"] == "Deluxe"

    def test_update_room(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        room_id = client.post(f"/accommodations/{accom_id}/rooms", json={
            "room_name": "Standard", "price_per_night": 50, "available_rooms": 2, "capacity": 2,
        }).get_json()["room_id"]

        resp = client.put(f"/rooms/{room_id}", json={
            "room_name": "Standard (renovated)", "price_per_night": 60,
            "available_rooms": 3, "capacity": 2, "images": [],
        })
        assert resp.status_code == 200
        fetched = client.get(f"/rooms/{room_id}").get_json()
        assert fetched["price_per_night"] == 60

    def test_delete_room(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        room_id = client.post(f"/accommodations/{accom_id}/rooms", json={
            "room_name": "Standard", "price_per_night": 50, "available_rooms": 2, "capacity": 2,
        }).get_json()["room_id"]

        resp = client.delete(f"/rooms/{room_id}")
        assert resp.status_code == 200
        assert client.get(f"/rooms/{room_id}").status_code == 404


class TestPriorities:
    def test_get_priority_returns_defaults_when_none_saved(self, client):
        resp = client.get("/priorities/12345")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["price_weight"] == 50
        assert body["location_weight"] == 50

    def test_put_priority_creates_if_missing(self, client):
        resp = client.put("/priorities/42", json={
            "price_weight": 80, "location_weight": 20, "facility_weight": 50, "review_weight": 50,
        })
        assert resp.status_code == 200
        fetched = client.get("/priorities/42").get_json()
        assert fetched["price_weight"] == 80

    def test_put_priority_updates_existing(self, client):
        client.put("/priorities/42", json={
            "price_weight": 80, "location_weight": 20, "facility_weight": 50, "review_weight": 50,
        })
        client.put("/priorities/42", json={
            "price_weight": 10, "location_weight": 90, "facility_weight": 50, "review_weight": 50,
        })
        fetched = client.get("/priorities/42").get_json()
        assert fetched["price_weight"] == 10
        assert fetched["location_weight"] == 90

    def test_delete_priority(self, client):
        client.put("/priorities/42", json={
            "price_weight": 80, "location_weight": 20, "facility_weight": 50, "review_weight": 50,
        })
        resp = client.delete("/priorities/42")
        assert resp.status_code == 200
        # Falls back to defaults after deletion
        fetched = client.get("/priorities/42").get_json()
        assert fetched["price_weight"] == 50


class TestListsAndListAccommodations:
    def test_create_and_get_user_lists(self, client):
        resp = client.post("/lists", json={"user_id": 1, "list_name": "Bali trip"})
        assert resp.status_code == 201

        lists = client.get("/lists/1").get_json()
        assert len(lists) == 1
        assert lists[0]["list_name"] == "Bali trip"

    def test_rename_list(self, client):
        list_id = client.post("/lists", json={"user_id": 1, "list_name": "Old name"}).get_json()["list_id"]
        client.put(f"/lists/{list_id}", json={"list_name": "New name"})
        lists = client.get("/lists/1").get_json()
        assert lists[0]["list_name"] == "New name"

    def test_add_and_get_list_accommodations(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        list_id = client.post("/lists", json={"user_id": 1, "list_name": "Trip"}).get_json()["list_id"]

        resp = client.post(f"/lists/{list_id}/accommodations", json={
            "accommodation_id": accom_id, "status": "Option",
        })
        assert resp.status_code == 201

        items = client.get(f"/lists/{list_id}/accommodations").get_json()
        assert len(items) == 1
        assert items[0]["accommodation_id"] == accom_id

    def test_filter_list_accommodations_by_status(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        list_id = client.post("/lists", json={"user_id": 1, "list_name": "Trip"}).get_json()["list_id"]
        client.post(f"/lists/{list_id}/accommodations", json={
            "accommodation_id": accom_id, "status": "Accepted",
        })

        matching = client.get(f"/lists/{list_id}/accommodations?status=Accepted").get_json()
        assert len(matching) == 1

        non_matching = client.get(f"/lists/{list_id}/accommodations?status=Rejected").get_json()
        assert len(non_matching) == 0

    def test_update_list_accommodation_status(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        list_id = client.post("/lists", json={"user_id": 1, "list_name": "Trip"}).get_json()["list_id"]
        list_accom_id = client.post(f"/lists/{list_id}/accommodations", json={
            "accommodation_id": accom_id, "status": "Option",
        }).get_json()["list_accom_id"]

        client.put(f"/list-accommodations/{list_accom_id}", json={"status": "Accepted", "room_id": None})
        items = client.get(f"/lists/{list_id}/accommodations").get_json()
        assert items[0]["status"] == "Accepted"

    def test_delete_list_cascades_list_accommodations(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        list_id = client.post("/lists", json={"user_id": 1, "list_name": "Trip"}).get_json()["list_id"]
        client.post(f"/lists/{list_id}/accommodations", json={"accommodation_id": accom_id})

        resp = client.delete(f"/lists/{list_id}")
        assert resp.status_code == 200
        assert client.get(f"/lists/{list_id}/accommodations").get_json() == []


class TestInternalEndpoint:
    def test_accommodations_with_price_includes_min_price(self, client):
        resp = client.get("/internal/accommodations-with-price")
        assert resp.status_code == 200
        results = resp.get_json()
        assert len(results) == 30
        for r in results:
            assert "min_price" in r
            assert r["min_price"] > 0

    def test_accommodations_with_price_returns_zero_when_no_rooms(self, client):
        accom_id = create_accommodation(client).get_json()["accommodation_id"]
        results = client.get("/internal/accommodations-with-price").get_json()
        match = next(r for r in results if r["accommodation_id"] == accom_id)
        assert match["min_price"] == 0