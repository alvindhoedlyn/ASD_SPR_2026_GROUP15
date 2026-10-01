"""
Shared, non-containerised, local MCP server for the group application.

Run locally (NOT in Docker):
    cd ai-services/mcp-server
    pip install -r requirements.txt
    python server.py
"""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import (
    TransportSecuritySettings,
)


# =========================================================
# MCP CONFIGURATION
# =========================================================

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "5200"))


mcp = FastMCP(
    "Group Travel App MCP Server",
    host=MCP_HOST,
    port=MCP_PORT,
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            f"localhost:{MCP_PORT}",
            f"127.0.0.1:{MCP_PORT}",
            f"host.docker.internal:{MCP_PORT}",
        ],
    ),
)


# =========================================================
# TOOL IMPORTS
# =========================================================

from tools_accommodation import (
    get_accommodations_by_city,
    get_accommodation_details,
)

from tools_budget import (
    get_budget_summary,
    get_budget_expenses,
)

from tools_itinerary import (
    get_available_journeys,
    generate_trip_itinerary,
    get_activity_categories,
)

from tools_location import (
    attractions_by_city as get_attractions_by_city,
    attraction_details as get_attraction_details,
)

from tools_flights import (
    get_flight_details,
    recommend_flights as run_flight_recommendation,
)


# =========================================================
# AVAILABLE TOOLS
# =========================================================

AVAILABLE_TOOLS = [
    "accommodations_by_city",   # student-3 / RenzoRobin
    "accommodation_details",    # student-3 / RenzoRobin

    "budget_summary",           # student-2 / KeyuanGan
    "budget_expenses",          # student-2 / KeyuanGan

    "available_journeys",       # Itinerary / Travel App
    "generate_trip_itinerary",  # Itinerary / Travel App

    "attractions_by_city",      # student-4 / TrongPhucDao
    "attraction_details",       # student-4 / TrongPhucDao
    "recommend_flights",        # student-5 / YajunNing
    "flight_details",           # student-5 / YajunNing
]


# =========================================================
# ACCOMMODATION TOOL SET
# =========================================================

@mcp.tool()
def accommodations_by_city(city_area: str):
    """Return accommodations located in a given city/area."""
    return get_accommodations_by_city(city_area)


@mcp.tool()
def accommodation_details(accommodation_id: int):
    """Return full details (including rooms) for one accommodation."""
    return get_accommodation_details(accommodation_id)


# =========================================================
# BUDGET TRACKER TOOL SET - KeyuanGan
# =========================================================

@mcp.tool()
def budget_summary():
    """
    Return the current Budget Tracker summary.

    Includes total budget, total spent, remaining budget,
    minimum price and maximum price.
    """
    return get_budget_summary()


@mcp.tool()
def budget_expenses():
    """
    Return all expense records from the Budget Tracker.
    """
    return get_budget_expenses()


# =========================================================
# ITINERARY TOOL SET
# =========================================================

@mcp.tool()
def available_journeys() -> str:
    """
    List all available journeys (id, label, locations)
    that a trip itinerary can be generated for.
    """
    return get_available_journeys()


# name= keeps the public tool name as "generate_trip_itinerary"
# while the Python function name stays distinct from the
# imported helper above.
@mcp.tool(name="generate_trip_itinerary")
def generate_trip_itinerary_tool(
    journey_id: int,
    duration: int,
    preferences: str = "General exploration",
    user_id: int = 1,
) -> str:
    """
    Generate and save an AI-written day-by-day trip itinerary.

    Args:
        journey_id:
            ID of the journey
            (get it from available_journeys).

        duration:
            Number of days for the trip (1-14).

        preferences:
            Free-text traveller preferences,
            e.g. "food and museums".

        user_id:
            ID of the user the trip is saved for.
    """
    return generate_trip_itinerary(
        journey_id,
        duration,
        preferences,
        user_id,
    )


@mcp.resource("travel://activity-categories")
def activity_categories_resource() -> str:
    """
    Activity categories and example activities
    used for itinerary generation.
    """
    return get_activity_categories()


# =========================================================
# ATTRACTION TOOL SET
# =========================================================

@mcp.tool()
def attractions_by_city(
    city: str,
    category: str | None = None,
) -> dict[str, Any]:
    """
    Return attractions in a city,
    optionally filtered by category.
    """
    return get_attractions_by_city(
        city,
        category,
    )


@mcp.tool()
def attraction_details(
    attraction_id: int,
) -> dict[str, Any]:
    """
    Return detailed information for one attraction.
    """
    return get_attraction_details(
        attraction_id
    )


# =========================================================
# FLIGHT TOOL SET - YajunNing
# =========================================================

@mcp.tool(name="recommend_flights")
def recommend_flights_tool(
    origin: str,
    destination: str,
    departure_date: str,
    max_budget: float,
    preference: str = "best_overall",
    return_date: str = "",
):
    """Recommend bounded catalogue flights using traveller search criteria."""
    return run_flight_recommendation(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        max_budget=max_budget,
        preference=preference,
        return_date=return_date,
    )


@mcp.tool(name="flight_details")
def flight_details_tool(flight_id: int):
    """Return one read-only catalogue record for a selected flight."""
    return get_flight_details(flight_id)


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    print(
        "Starting Group Travel App MCP Server..."
    )

    print(
        "Server status: RUNNING"
    )

    print(
        "Interact with MCP tools from a second terminal."
    )

    print(
        "Available tools:"
    )

    for tool in AVAILABLE_TOOLS:
        print(f"- {tool}")

    print(
        f"Streamable HTTP endpoint: "
        f"http://localhost:{MCP_PORT}/mcp"
    )

    mcp.run(
        transport="streamable-http"
    )
