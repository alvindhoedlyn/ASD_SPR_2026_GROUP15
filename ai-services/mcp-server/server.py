"""
Shared, non-containerised, local MCP server for the group application.

Run locally (NOT in Docker):
    cd ai-services/mcp-server
    pip install -r requirements.txt
    python server.py
"""

from mcp.server.fastmcp import FastMCP

from tools_accommodation import (
    get_accommodations_by_city,
    get_accommodation_details,
)

from tools_itinerary import (
    get_available_journeys,
    generate_trip_itinerary,
    get_activity_categories,
)

mcp = FastMCP("Group Travel App MCP Server")

AVAILABLE_TOOLS = [
    "accommodations_by_city",   # student-3 / RenzoRobin
    "accommodation_details",    # student-3 / RenzoRobin
    "available_journeys",       # Itinerary / Travel App
    "generate_trip_itinerary",  # Itinerary / Travel App
]

# ACCOMMODATION TOOL SET----
@mcp.tool()
def accommodations_by_city(city_area: str):
    """Return accommodations located in a given city/area."""
    return get_accommodations_by_city(city_area)


@mcp.tool()
def accommodation_details(accommodation_id: int):
    """Return full details (including rooms) for one accommodation."""
    return get_accommodation_details(accommodation_id)

# ACCOMMODATION TOOL SET----

# ITINERARY TOOL SET----
@mcp.tool()
def available_journeys() -> str:
    """Fetch all available travel journeys and their locations from the database service."""
    return get_available_journeys()


@mcp.tool()
def generate_trip_itinerary_tool(journey_id: int, duration: int, preferences: str = "General exploration", user_id: int = 1) -> str:
    """Generate a custom AI travel itinerary set based on desired journey ID and duration."""
    return generate_trip_itinerary(journey_id, duration, preferences, user_id)


@mcp.resource("travel://activity-categories")
def activity_categories_resource() -> str:
    """Expose available activity categories and options as an MCP resource."""
    return get_activity_categories()

# ITINERARY TOOL SET----


if __name__ == "__main__":
    print("Starting Group Travel App MCP Server...")
    print("Server status: RUNNING")
    print("Interact with MCP tools from a second terminal.")
    print("Available tools:")
    for tool in AVAILABLE_TOOLS:
        print(f"- {tool}")
    mcp.run()