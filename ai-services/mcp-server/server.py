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

mcp = FastMCP("Group Travel App MCP Server")

AVAILABLE_TOOLS = [
    "accommodations_by_city",   # student-3 / RenzoRobin
    "accommodation_details",    # student-3 / RenzoRobin
]


@mcp.tool()
def accommodations_by_city(city_area: str):
    """Return accommodations located in a given city/area."""
    return get_accommodations_by_city(city_area)


@mcp.tool()
def accommodation_details(accommodation_id: int):
    """Return full details (including rooms) for one accommodation."""
    return get_accommodation_details(accommodation_id)


if __name__ == "__main__":
    print("Starting Group Travel App MCP Server...")
    print("Server status: RUNNING")
    print("Interact with MCP tools from a second terminal.")
    print("Available tools:")
    for tool in AVAILABLE_TOOLS:
        print(f"- {tool}")
    mcp.run()