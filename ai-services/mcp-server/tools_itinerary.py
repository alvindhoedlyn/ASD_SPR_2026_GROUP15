from mcp.server.fastmcp import FastMCP
import os
import requests

# Initialize FastMCP server
mcp = FastMCP("Travel App Itinerary MCP Server")

# Pull database service URL from environment (matching your app.py)
DB_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://student-AlvindhoEdlyn-database:6001")

@mcp.tool()
def get_available_journeys() -> str:
    """Fetch all available travel journeys and their locations from the database service."""
    try:
        response = requests.get(f"{DB_SERVICE_URL}/api/journeys", timeout=5)
        if response.status_code == 200:
            return str(response.json())
        return f"Error: Received status code {response.status_code}"
    except Exception as e:
        return f"Database service unreachable: {str(e)}"

@mcp.tool()
def generate_trip_itinerary(journey_id: int, duration: int, preferences: str = "General exploration", user_id: int = 1) -> str:
    """Generate a custom AI travel itinerary set based on desired journey ID and duration."""
    payload = {
        "journeyId": journey_id,
        "duration": duration,
        "preferences": preferences,
        "userId": user_id
    }
    try:
        response = requests.post(f"{DB_SERVICE_URL}/api/trips/generate", json=payload, timeout=10)
        if response.status_code == 201:
            return str(response.json())
        return f"Failed to generate trip: {response.text}"
    except Exception as e:
        return f"Error connecting to backend trip generation: {str(e)}"

@mcp.resource("travel://activity-categories")
def get_activity_categories() -> str:
    """Expose available activity categories and options as an MCP resource."""
    categories = {
        "Sightseeing": ["City tour", "Old town walk", "Harbor cruise", "Viewpoint photography"],
        "Adventure": ["Hiking trail", "Kayaking", "Snorkeling", "Rock climbing", "Bike rental"],
        "Culture": ["Museum visit", "Art gallery tour", "Historic site walk", "Local theater"],
        "Relaxation": ["Beach day", "Botanical gardens walk", "Spa visit", "Park picnic"],
        "Food & Drink": ["Local market tasting", "Cafe hopping", "Street food tour", "Cooking class"],
        "Shopping": ["Boutique shopping", "Souvenir hunting", "Craft market visit"]
    }
    return str(categories)

if __name__ == "__main__":
    # Runs the server using standard input/output (stdio) transport for local AI clients
    mcp.run()