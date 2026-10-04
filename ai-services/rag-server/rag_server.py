"""
FastMCP wrapper around the RAG pipeline (for terminal / MCP-client testing,
same pattern as ai-services/mcp-server/server.py).

Run:
    cd ai-services/rag-server
    python rag_server.py
"""

from mcp.server.fastmcp import FastMCP

from rag_pipeline import (
    answer_question as answer_question_impl,
    refresh_corpus as refresh_corpus_impl,
    retrieve_activities as retrieve_activities_impl,
    retrieve_context as retrieve_context_impl,
    search_itinerary as search_itinerary_impl,
)

mcp = FastMCP("Group Travel App RAG MCP")
AVAILABLE_TOOLS = ["refresh_corpus", "retrieve_context", "retrieve_activities", "search_itinerary", "answer_question"]


@mcp.tool()
def refresh_corpus(caller: str = "student"):
    return refresh_corpus_impl(caller=caller)


@mcp.tool()
def retrieve_context(query: str, k: int = 5, caller: str = "student"):
    return retrieve_context_impl(query=query, k=k, caller=caller)


@mcp.tool()
def retrieve_activities(location: str, weather: str | None = None, k: int = 4, caller: str = "student"):
    return retrieve_activities_impl(location=location, weather=weather, k=k, caller=caller)


@mcp.tool()
def search_itinerary(query: str, caller: str = "student"):
    # always the top 5 results (k@5) with precision_at_5
    return search_itinerary_impl(query=query, caller=caller)


@mcp.tool()
def answer_question(query: str, k: int = 5, caller: str = "student"):
    return answer_question_impl(query=query, k=k, caller=caller)


if __name__ == "__main__":
    print("Starting Group Travel App RAG MCP Server...")
    print("Server status: RUNNING")
    print("Interact with RAG tools from a second terminal.")
    print("Available tools:")
    for tool in AVAILABLE_TOOLS:
        print(f"- {tool}")
    mcp.run()