import os

import requests


DEFAULT_DATABASE_URL = "http://localhost:5404"


def collect(app_dir, repo_root):
    database_url = os.getenv(
        "DATABASE_BASE_URL",
        DEFAULT_DATABASE_URL
    )

    try:
        health_response = requests.get(
            f"{database_url}/health",
            timeout=5
        )

        if health_response.status_code != 200:
            return False, (
                "Database health check failed with status "
                f"{health_response.status_code}."
            )

        places_response = requests.get(
            f"{database_url}/places",
            timeout=5
        )

        requests_response = requests.get(
            f"{database_url}/recommendation-requests",
            timeout=5
        )

        saved_response = requests.get(
            f"{database_url}/saved-places",
            timeout=5
        )

        places_response.raise_for_status()
        requests_response.raise_for_status()
        saved_response.raise_for_status()

        places = places_response.json()
        recommendation_requests = requests_response.json()
        saved_places = saved_response.json()

        if not isinstance(places, list):
            return False, "The places endpoint did not return a list."

        if not isinstance(recommendation_requests, list):
            return False, (
                "The recommendation requests endpoint did not return a list."
            )

        if not isinstance(saved_places, list):
            return False, "The saved places endpoint did not return a list."

        if len(places) == 0:
            return False, "The database contains no attractions."

        place_ids = {
            place["attraction_id"]
            for place in places
        }

        invalid_saved_places = []

        for saved_place in saved_places:
            if saved_place["attraction_id"] not in place_ids:
                invalid_saved_places.append(
                    saved_place["saved_place_id"]
                )

        if invalid_saved_places:
            return False, (
                "Saved places contain invalid attraction references: "
                + str(invalid_saved_places)
            )

        cities = sorted({
            place["city"]
            for place in places
        })

        categories = sorted({
            place["category"]
            for place in places
        })

        evidence = (
            f"Database API is running at {database_url}. "
            f"It returned {len(places)} attractions, "
            f"{len(recommendation_requests)} recommendation requests, "
            f"and {len(saved_places)} saved places. "
            f"Available cities: {', '.join(cities)}. "
            f"Available categories: {', '.join(categories)}. "
            "All returned saved places reference valid attractions."
        )

        return True, evidence

    except requests.ConnectionError:
        return False, (
            f"Database service is not available at {database_url}. "
            "Start the database container before running the review."
        )

    except requests.Timeout:
        return False, "The database service request timed out."

    except requests.RequestException as error:
        return False, f"Database API request failed: {error}"

    except (KeyError, TypeError, ValueError) as error:
        return False, f"Database response was invalid: {error}"