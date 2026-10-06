"""Collect live grounded and insufficient-context RAG evidence."""

import os
from pathlib import Path

import requests


DEFAULT_BACKEND_URL = "http://localhost:5004"
REQUEST_TIMEOUT = 180

GROUNDED_QUERY = (
    "What accessibility information does the "
    "Sydney Opera House have?"
)
INSUFFICIENT_QUERY = "Which attraction offers guided tours on Mars?"


def _ask_question(backend_url, query):
    response = requests.post(
        f"{backend_url}/api/rag/answer",
        headers={"X-RAG-Mode": "on"},
        json={"query": query, "k": 5},
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        return False, (
            f"RAG query returned HTTP {response.status_code}: "
            f"{response.text[:200]}"
        ), None

    return True, "", response.json()


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    """Validate grounded and refusal behavior through the backend."""
    del app_dir, repo_root

    backend_url = os.getenv(
        "BACKEND_BASE_URL",
        DEFAULT_BACKEND_URL
    ).rstrip("/")

    try:
        ok, error, grounded = _ask_question(
            backend_url,
            GROUNDED_QUERY
        )

        if not ok:
            return False, error

        citations = grounded.get("citations")
        confidence = grounded.get("confidence_category")
        answer = str(grounded.get("answer", "")).strip()

        if grounded.get("status") != "success":
            return False, (
                "The approved attraction query did not return success."
            )

        if not answer or not isinstance(citations, list) or not citations:
            return False, (
                "The grounded attraction response is missing its answer "
                "or source citations."
            )

        if str(confidence).casefold() == "insufficient":
            return False, (
                "The approved attraction query returned insufficient "
                "confidence."
            )

        if not all(
            citation.get("source_id")
            and citation.get("chunk_id")
            and citation.get("authority_tier")
            for citation in citations
        ):
            return False, "A RAG citation is missing traceability fields."

        ok, error, insufficient = _ask_question(
            backend_url,
            INSUFFICIENT_QUERY
        )

        if not ok:
            return False, error

        if insufficient.get("status") != "insufficient_context":
            return False, (
                "The unsupported Mars query was not rejected as "
                "insufficient context."
            )

        if insufficient.get("citations") != []:
            return False, (
                "The insufficient-context response unexpectedly included "
                "citations."
            )

        if insufficient.get("confidence_category") != "Insufficient":
            return False, (
                "The insufficient-context response has the wrong "
                "confidence category."
            )

        evidence = (
            f"Attraction RAG backend is reachable at {backend_url}. "
            f"Grounded query returned confidence {confidence}, "
            f"{len(citations)} citation(s), and answer: {answer} "
            "The unsupported Mars query correctly returned "
            "insufficient_context with no citations."
        )

        return True, evidence

    except requests.ConnectionError:
        return False, (
            f"The attraction backend is unavailable at {backend_url}."
        )
    except requests.Timeout:
        return False, "The attraction RAG validation request timed out."
    except (requests.RequestException, ValueError) as error:
        return False, f"Attraction RAG validation failed: {error}"
