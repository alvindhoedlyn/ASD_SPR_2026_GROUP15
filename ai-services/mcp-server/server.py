"""
Shared, non-containerised, local MCP server for the group application.

Run locally (NOT in Docker):
    cd ai-services/mcp-server
    pip install -r requirements.txt
    python server.py
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Group Travel App MCP Server")

from tools_accommodation import (
    get_accommodations_by_city,
    get_accommodation_details,
)

from tools_itinerary import (
    get_available_journeys,
    generate_trip_itinerary,
    get_activity_categories,
)

AVAILABLE_TOOLS = [
    "accommodations_by_city",   # student-3 / RenzoRobin
    "accommodation_details",    # student-3 / RenzoRobin
    "available_journeys",       # Itinerary / Travel App (AlvindhoEdlyn)
    "generate_trip_itinerary",  # Itinerary / Travel App (AlvindhoEdlyn)
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
    """List all available journeys (id, label, locations) that a trip itinerary can be generated for."""
    return get_available_journeys()


# name= keeps the public tool name as "generate_trip_itinerary" while the Python
# function name stays distinct from the imported helper above.
@mcp.tool(name="generate_trip_itinerary")
def generate_trip_itinerary_tool(
    journey_id: int,
    duration: int,
    preferences: str = "General exploration",
    user_id: int = 1,
) -> str:
    """Generate and save an AI-written day-by-day trip itinerary.

    Args:
        journey_id: ID of the journey (get it from available_journeys).
        duration: Number of days for the trip (1-14).
        preferences: Free-text traveller preferences, e.g. "food and museums".
        user_id: ID of the user the trip is saved for.
    """
    return generate_trip_itinerary(journey_id, duration, preferences, user_id)


@mcp.resource("travel://activity-categories")
def activity_categories_resource() -> str:
    """Activity categories and example activities used for itinerary generation."""
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