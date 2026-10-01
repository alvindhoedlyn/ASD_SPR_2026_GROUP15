"""
Corpus loader for the Budget Tracker feature (Student 2 - Keyuan Gan).

Loads the Budget Tracker knowledge base into the group's shared RAG corpus.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_FILE = BASE_DIR / "knowledge" / "budget_tracker.md"


def load_budget_chunks():
    if not KNOWLEDGE_FILE.exists():
        return [{
            "chunk_id": "budget_knowledge_unavailable",
            "source_id": "knowledge/budget_tracker.md",
            "authority_tier": "tier_1",
            "text": "Budget Tracker knowledge base is unavailable.",
            "metadata": {
                "source_type": "budget_knowledge",
                "error": True,
            },
        }]

    content = KNOWLEDGE_FILE.read_text(encoding="utf-8")

    sections = [
        section.strip()
        for section in content.split("## ")
        if section.strip()
    ]

    chunks = []

    for index, section in enumerate(sections, start=1):
        chunks.append({
            "chunk_id": f"budget_{index}",
            "source_id": "knowledge/budget_tracker.md",
            "authority_tier": "tier_1",
            "text": section,
            "metadata": {
                "source_type": "budget_knowledge",
                "feature": "budget_tracker",
            },
        })

    return chunks
