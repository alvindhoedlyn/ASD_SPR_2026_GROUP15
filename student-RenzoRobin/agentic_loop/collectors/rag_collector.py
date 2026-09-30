"""
RAG validation collector for the Accommodation Recommender.

Calls the /rag/answer route on YOUR OWN running backend
(student-RenzoRobin-backend), which proxies to the shared, non-
containerised RAG server. Two fixed test queries are used deliberately:
one that SHOULD ground successfully (a real city in the corpus), and one
that SHOULD correctly return insufficient-context (a city that does not
exist in the corpus) — together they demonstrate both required RAG
behaviours from the brief: grounded responses with citations/confidence,
and refusing to answer when relevant context is unavailable.

Returns (ok, evidence) matching the shared collector contract.
"""
from pathlib import Path

import requests

BACKEND_URL = "http://localhost:5003"
REQUEST_TIMEOUT = 180  # local LLM generation can be slow, especially on larger models

GROUNDED_QUERY = "What accommodation are in Kyoto that has breakfast?"
INSUFFICIENT_QUERY = "What accommodation are in Tokyo?"


def _call_rag_answer(query: str) -> tuple[bool, str]:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/rag/answer",
            json={"query": query, "k": 5},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        return False, f"'{query}': request failed — {exc}"

    if resp.status_code == 403:
        return False, f"'{query}': RAG mode is disabled on the backend."
    if resp.status_code not in (200,):
        return False, f"'{query}': HTTP {resp.status_code} — {resp.text[:200]}"

    body = resp.json()
    status = body.get("status")
    confidence = body.get("confidence_category")
    citations = body.get("citations", [])

    if status == "success":
        return True, (
            f"'{query}': status=success, confidence={confidence}, "
            f"citations={len(citations)}, answer='{(body.get('answer') or '')[:150]}...'"
        )
    if status == "insufficient_context":
        return True, f"'{query}': status=insufficient_context, confidence={confidence}, citations=0 (expected)"

    return False, f"'{query}': unexpected status '{status}' — {body}"


def collect(app_dir: Path, repo_root: Path) -> tuple[bool, str]:
    lines = []
    all_ok = True

    ok1, line1 = _call_rag_answer(GROUNDED_QUERY)
    all_ok = all_ok and ok1
    lines.append(line1)

    ok2, line2 = _call_rag_answer(INSUFFICIENT_QUERY)
    all_ok = all_ok and ok2
    lines.append(line2)

    evidence = "\n".join(lines)
    return all_ok, evidence