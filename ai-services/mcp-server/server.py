"""
Shared, non-containerised, local MCP server for the group application.

Run locally (NOT in Docker):
    cd ai-services/mcp-server
    pip install -r requirements.txt
    python server.py

MCP endpoint:
    http://localhost:8000/mcp
"""

from mcp.server.fastmcp import FastMCP

from tools_accommodation import (
    get_accommodations_by_city,
    get_accommodation_details,
)

from tools_budget import (
    get_budget_summary,
    get_budget_expenses,
)


# =========================================================
# Shared MCP Server
# =========================================================

mcp = FastMCP(
    "Group Travel App MCP Server",
    host="0.0.0.0",
    port=8000,
)


AVAILABLE_TOOLS = [
    "accommodations_by_city",   # student-3 / RenzoRobin
    "accommodation_details",    # student-3 / RenzoRobin
    "budget_summary",           # student-2 / KeyuanGan
    "budget_expenses",          # student-2 / KeyuanGan
]


# =========================================================
# Accommodation Tools - RenzoRobin
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
# Budget Tracker Tools - KeyuanGan
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
# Server Start
# =========================================================

if __name__ == "__main__":
    print("Starting Group Travel App MCP Server...")
    print("Transport: streamable-http")
    print("MCP endpoint: http://localhost:8000/mcp")
    print("Available tools:")

    for tool in AVAILABLE_TOOLS:
        print(f"- {tool}")

    mcp.run(transport="streamable-http")