import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


DATABASE_DIR = Path(__file__).resolve().parents[1] / "database"
sys.path.insert(0, str(DATABASE_DIR))
SPEC = importlib.util.spec_from_file_location("flight_database_app", DATABASE_DIR / "app.py")
database_app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(database_app)


class SavedFlightCrudTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_app.DATABASE_PATH = str(Path(self.temp_directory.name) / "test-flights.db")
        database_app.initialize_database(database_app.DATABASE_PATH)
        self.client = database_app.app.test_client()

    def tearDown(self):
        self.temp_directory.cleanup()

    def create_saved_flight(self, username="Yajun"):
        return self.client.post(
            "/saved-flights",
            json={
                "username": username,
                "flight_id": 2,
                "departure_date": "2026-09-10",
                "return_date": "2026-09-17",
            },
        )

    def test_user_can_create_read_update_and_delete_saved_flight(self):
        created = self.create_saved_flight()
        self.assertEqual(created.status_code, 201)
        saved_flight = created.get_json()
        self.assertEqual(saved_flight["flight_number"], "JQ11")
        self.assertEqual(saved_flight["price_aud"], 620)

        listed = self.client.get("/saved-flights?username=Yajun")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()), 1)

        updated = self.client.put(
            f"/saved-flights/{saved_flight['id']}",
            json={"username": "Yajun", "status": "booked", "note": "Seat selected"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["status"], "booked")
        self.assertEqual(updated.get_json()["note"], "Seat selected")
        self.assertEqual(updated.get_json()["price_aud"], 620)

        deleted = self.client.delete(f"/saved-flights/{saved_flight['id']}?username=Yajun")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/saved-flights?username=Yajun").get_json(), [])

    def test_saved_flights_are_isolated_by_username(self):
        self.create_saved_flight(username="Yajun")
        other_user = self.client.get("/saved-flights?username=OtherUser")
        self.assertEqual(other_user.status_code, 200)
        self.assertEqual(other_user.get_json(), [])

    def test_duplicate_saved_flight_is_rejected(self):
        self.assertEqual(self.create_saved_flight().status_code, 201)
        duplicate = self.create_saved_flight()
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already saved", duplicate.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
