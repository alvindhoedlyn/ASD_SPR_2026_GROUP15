"""
Client for the JourneyBuddy shared local RAG server.

The Budget Tracker backend runs inside Docker, while the shared
RAG server runs locally on the host machine.

Default RAG endpoint:
    http://host.docker.internal:8100

The URL can be overridden using the RAG_SERVER_URL
environment variable.
"""

import os

import requests


RAG_SERVER_URL = os.getenv(
    "RAG_SERVER_URL",
    "http://host.docker.internal:8100",
)


def query_rag(question):
    """
    Send a question to the shared RAG server.

    Returns the RAG response containing:
    - question
    - answer
    - sources
    - confidence
    - retrieved_context
    """

    if not question or not question.strip():
        raise ValueError(
            "RAG question cannot be empty."
        )

    response = requests.post(
        f"{RAG_SERVER_URL}/query",
        json={
            "question": question.strip(),
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


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