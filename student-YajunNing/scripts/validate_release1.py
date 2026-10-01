"""Print concise Release 1 validation evidence for Student 5.

Prerequisites: containerised Flight services plus local MCP and RAG servers.
Run from the repository root:
    python student-YajunNing/scripts/validate_release1.py
"""

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_URL = "http://localhost:5005"


def request_json(method, path, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{BACKEND_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=45) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def show(title, status_code, body):
    print(f"\n=== {title} (HTTP {status_code}) ===")
    print(json.dumps(body, indent=2))


def main():
    search = {
        "origin": "Sydney",
        "destination": "Tokyo",
        "departure_date": "2026-10-10",
        "return_date": "2026-10-17",
        "max_budget": 1000,
        "preference": "best_overall",
    }
    checks = [
        ("Release 1 status", "GET", "/api/release1/status", None),
        ("MCP registered-tool result", "POST", "/api/mcp/recommend-flights", search),
        (
            "RAG grounded result",
            "POST",
            "/api/rag/answer",
            {"query": "Which direct Sydney to Tokyo flight costs less than AUD 700?", "k": 5},
        ),
        (
            "RAG insufficient-context guard",
            "POST",
            "/api/rag/answer",
            {"query": "Which flight includes a free helicopter transfer?", "k": 5},
        ),
    ]
    try:
        for title, method, path, payload in checks:
            status_code, body = request_json(method, path, payload)
            show(title, status_code, body)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
