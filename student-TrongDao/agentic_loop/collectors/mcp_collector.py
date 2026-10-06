"""Collect live evidence for the attraction MCP integration."""

import os
from pathlib import Path

import requests


DEFAULT_BACKEND_URL = "http://localhost:5004"
REQUEST_TIMEOUT = 30


def _call_tool(backend_url, tool_name, arguments):
    response = requests.post(
        f"{backend_url}/api/mcp/call",
        headers={"X-MCP-Mode": "on"},
        json={
            "tool": tool_name,
            "arguments": arguments
        },
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        return False, (
            f"{tool_name} returned HTTP {response.status_code}: "
            f"{response.text[:200]}"
        ), None

    body = response.json()
    structured_content = (
        body.get("result", {}).get("structuredContent")
    )

    if not isinstance(structured_content, dict):
        return False, (
            f"{tool_name} returned no structured MCP content."
        ), None

    return True, "", structured_content


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    """Validate both attraction tools through the feature backend."""
    del app_dir, repo_root

    backend_url = os.getenv(
        "BACKEND_BASE_URL",
        DEFAULT_BACKEND_URL
    ).rstrip("/")

    evidence = []

    try:
        ok, error, city_result = _call_tool(
            backend_url,
            "attractions_by_city",
            {
                "city": "Sydney",
                "category": "nature"
            }
        )

        if not ok:
            return False, error

        attractions = city_result.get("attractions")

        if (
            city_result.get("city") != "Sydney"
            or not isinstance(attractions, list)
            or not attractions
        ):
            return False, (
                "attractions_by_city returned an invalid or empty result."
            )

        if any(
            attraction.get("category", "").casefold() != "nature"
            for attraction in attractions
        ):
            return False, (
                "attractions_by_city returned an attraction outside "
                "the requested nature category."
            )

        evidence.append(
            "attractions_by_city returned "
            f"{len(attractions)} Sydney nature attraction(s) "
            "as structured content."
        )

        attraction_id = attractions[0].get("attraction_id")

        ok, error, details_result = _call_tool(
            backend_url,
            "attraction_details",
            {"attraction_id": attraction_id}
        )

        if not ok:
            return False, error

        if details_result.get("attraction_id") != attraction_id:
            return False, (
                "attraction_details returned a different attraction ID."
            )

        evidence.append(
            "attraction_details returned attraction ID "
            f"{attraction_id} ({details_result.get('attraction_name')}) "
            "as structured content."
        )

        return True, (
            f"Attraction MCP backend is reachable at {backend_url}. "
            + " ".join(evidence)
        )

    except requests.ConnectionError:
        return False, (
            f"The attraction backend is unavailable at {backend_url}."
        )
    except requests.Timeout:
        return False, "The attraction MCP validation request timed out."
    except (requests.RequestException, ValueError) as error:
        return False, f"Attraction MCP validation failed: {error}"
