"""HTTP client for the shared, local, non-containerised RAG server."""

import os
from typing import Any

import requests


def rag_enabled() -> bool:
    return os.getenv("RAG_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def rag_service_url() -> str:
    return os.getenv("RAG_SERVICE_URL", "http://host.docker.internal:8100")


def ask_rag(query: str, k: int = 5) -> dict[str, Any]:
    if not rag_enabled():
        raise RuntimeError("RAG mode is disabled")
    response = requests.post(
        f"{rag_service_url()}/query",
        json={"question": query},
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()

    confidence = str(result.get("confidence", "insufficient")).strip().lower()
    status = "insufficient_context" if confidence == "insufficient" else "success"
    citations = [
        {
            "source_id": f"{source.get('document', 'unknown')}#{source.get('section', 'unknown')}",
            "document": source.get("document"),
            "section": source.get("section"),
        }
        for source in result.get("sources", [])
    ]

    return {
        "status": status,
        "query": result.get("question", query),
        "answer": result.get("answer", ""),
        "citations": citations,
        "confidence_category": confidence.capitalize(),
        "retrieved_context": result.get("retrieved_context", [])[:k],
        "model": result.get("model"),
        "generation_mode": result.get("generation_mode", "not_applicable"),
        "service": result.get("service", "journeybuddy-shared-rag"),
    }
