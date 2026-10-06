"""
Client for the JourneyBuddy shared local RAG server.

The Budget Tracker backend runs inside Docker, while the shared
RAG server runs locally on the host machine.

Default RAG endpoint:
    http://host.docker.internal:5100

The URL can be overridden using the RAG_SERVER_URL
environment variable.
"""

import os

import requests


RAG_SERVER_URL = os.getenv(
    "RAG_SERVER_URL",
    "http://host.docker.internal:5100",
)


def query_rag(question):
    """
    Send a question to the group's shared RAG server
    and adapt the shared response for the Budget Tracker UI.
    """

    if not question or not question.strip():
        raise ValueError("RAG question cannot be empty.")

    response = requests.post(
        f"{RAG_SERVER_URL}/answer",
        json={
            "query": question.strip(),
            "k": 5,
            "caller": "student-KeyuanGan",
        },
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    result["confidence"] = result.get(
        "confidence_category",
        "unknown",
    )

    citations = result.get("citations", [])

    result["sources"] = [
        {
            "document": citation.get("source_id", "Unknown source"),
            "section": citation.get("chunk_id", ""),
        }
        for citation in citations
    ]

    return result


def check_rag_health():
    """
    Check whether the shared RAG server is available.
    """

    response = requests.get(
        f"{RAG_SERVER_URL}/health",
        timeout=5,
    )

    response.raise_for_status()

    return response.json()
