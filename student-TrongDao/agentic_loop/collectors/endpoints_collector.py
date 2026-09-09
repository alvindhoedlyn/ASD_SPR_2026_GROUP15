import os
import re

import requests


DEFAULT_BACKEND_URL = "http://localhost:5104"


def collect(app_dir, repo_root):
    backend_url = os.getenv(
        "BACKEND_BASE_URL",
        DEFAULT_BACKEND_URL
    )

    backend_file = app_dir / "backend" / "app.py"

    if not backend_file.exists():
        return False, "The backend app.py file could not be found."

    backend_code = backend_file.read_text(encoding="utf-8")

    route_pattern = re.compile(
        r'@app\.(?:route|get|post|put|delete)'
        r'\("([^"]+)"'
    )

    routes = sorted(set(route_pattern.findall(backend_code)))

    if not routes:
        return False, "No Flask API routes were found."

    safe_checks = [
        ("Health endpoint", f"{backend_url}/health"),
        ("Places endpoint", f"{backend_url}/api/places"),
        (
            "Saved places endpoint",
            f"{backend_url}/api/saved-places"
            "?journey_id=AGENTIC-EVIDENCE"
        )
    ]

    results = []
    failed_checks = []

    try:
        for name, url in safe_checks:
            response = requests.get(url, timeout=5)

            results.append(
                f"{name} returned HTTP {response.status_code}"
            )

            if response.status_code != 200:
                failed_checks.append(name)

        if failed_checks:
            return False, (
                "Endpoint checks failed: "
                + ", ".join(failed_checks)
                + ". "
                + "; ".join(results)
            )

        evidence = (
            f"Found {len(routes)} Flask routes in backend/app.py. "
            f"Routes: {', '.join(routes)}. "
            f"Live checks at {backend_url}: "
            + "; ".join(results)
            + "."
        )

        return True, evidence

    except requests.ConnectionError:
        return False, (
            f"The backend service is not available at {backend_url}. "
            "Start the backend and database containers first."
        )

    except requests.Timeout:
        return False, "A backend endpoint request timed out."

    except requests.RequestException as error:
        return False, f"Endpoint request failed: {error}"   