"""
Endpoints evidence collector for the Accommodation Recommender backend.

Parses actual @app.route decorators out of backend/app.py, then makes
REAL HTTP requests to the running Flask service and records status
codes + response times. This is live evidence, not a static file check —
requires the backend to actually be running (docker compose up).

Adapted from the ASD course's Lab 04 endpoints_collector.py.
"""
import os
import re
from pathlib import Path

import requests

ROUTE_PATTERN = re.compile(r'@app\.route\("([^"]+)"(?:,\s*methods=\[([^\]]*)\])?\)')


def _methods_from_match(methods_str: str | None) -> list[str]:
    if not methods_str:
        return ["GET"]
    return [m.strip().strip('"').strip("'") for m in methods_str.split(",")]


def _sample_path(path: str) -> str:
    """Fill in Flask <int:...> / <name> placeholders with a harmless sample value."""
    path = re.sub(r"<int:\w+>", "1", path)
    path = re.sub(r"<\w+>", "1", path)
    return path


def _test_endpoint(base_url: str, method: str, path: str) -> str:
    url = f"{base_url}{path}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=3)
        elif method.upper() == "POST":
            response = requests.post(url, json={}, timeout=3)
        elif method.upper() == "PUT":
            # Empty body is safe: every PUT handler in backend/app.py falls
            # back to the existing row value for any field not present in
            # the payload, so this re-saves current data without mutating it.
            response = requests.put(url, json={}, timeout=3)
        else:
            return f"{method.upper()} {path} [SKIPPED - not live-tested to avoid deleting real data]"

        elapsed_ms = int(response.elapsed.total_seconds() * 1000)
        return f"{method.upper()} {path} returned {response.status_code} in {elapsed_ms}ms"

    except requests.exceptions.ConnectionError:
        return f"{method.upper()} {path} [CONNECTION REFUSED - backend not running]"
    except requests.exceptions.Timeout:
        return f"{method.upper()} {path} [TIMEOUT]"
    except Exception as exc:
        return f"{method.upper()} {path} [ERROR: {type(exc).__name__}]"

def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    backend_base_url = os.getenv("BACKEND_BASE_URL", "http://localhost:5003")

    route_file = app_dir / "backend" / "app.py"
    if not route_file.exists():
        return False, f"Missing route file: {route_file.relative_to(app_dir)}"

    content = route_file.read_text(encoding="utf-8")
    endpoints: list[tuple[str, str]] = []
    for path, methods_str in ROUTE_PATTERN.findall(content):
        for method in _methods_from_match(methods_str):
            endpoints.append((method, _sample_path(path)))

    if not endpoints:
        return False, "No Flask routes found in backend/app.py."

    evidence_parts = []
    live_tested = 0
    connection_failures = 0
    for method, path in sorted(set(endpoints)):
        result = _test_endpoint(backend_base_url, method, path)
        evidence_parts.append(result)
        if "SKIPPED" not in result:
            live_tested += 1
            if "CONNECTION REFUSED" in result:
                connection_failures += 1

    evidence = "Live endpoint evidence: " + "; ".join(evidence_parts) + "."

    # Success requires at least one endpoint to have actually gotten a
    # real HTTP response — not just "not every endpoint failed", since
    # unsupported-method entries don't count as attempts either way and
    # could otherwise mask a fully unreachable backend.
    if live_tested == 0 or connection_failures == live_tested:
        return False, (
            "Backend not running. Start it first "
            "(docker compose up student-RenzoRobin-backend), then run the agentic loop."
        )

    return True, evidence