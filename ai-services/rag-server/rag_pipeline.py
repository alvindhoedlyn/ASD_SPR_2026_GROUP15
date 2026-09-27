"""
Shared, non-containerised, local RAG pipeline for the group application.

Mirrors the pattern from Lab 08: local corpus -> chunk -> embed -> ChromaDB
-> retrieve top-k -> grounded LLM answer with citations + confidence.

Runs locally (NOT in Docker). Uses a simple deterministic hash-based
embedding (no external embedding API / model download required) — good
enough for local semantic-ish similarity search in this assignment.
"""

import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from openai import OpenAI

from corpus_accommodation import load_accommodation_chunks

# Other students: import your own corpus_<feature>.py loader here, e.g.
# from corpus_flights import load_flight_chunks
# from corpus_location import load_location_chunks

BASE_DIR = Path(__file__).resolve().parent
CORPUS_PATH = BASE_DIR / "corpus" / "corpus.jsonl"
AUDIT_PATH = BASE_DIR / "rag-audit.jsonl"
CHROMA_PATH = BASE_DIR / "chroma"

COLLECTION_NAME = "group_travel_app_context"
EMBED_VECTOR_SIZE = 256

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# Swapped from qwen2.5:0.5b -> llama3.1:8b to test whether a larger model
# reduces facility-hallucination on grounded answers (see report notes).
# Already used elsewhere in the group's stack (student-TrongDao review
# pipeline), so it may already be pulled into the shared ai-mode volume.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
client = OpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama")

# Common words filtered out before keyword-overlap scoring, so they don't
# swamp the ranking (they appear in almost every query AND almost every
# chunk's boilerplate text, so they carry no discriminating signal).
STOPWORDS = {
    "a", "an", "and", "are", "at", "for", "in", "is", "of", "on",
    "or", "the", "to", "what", "which", "with", "from",
}


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in tokens if t not in STOPWORDS}


def _boilerplate_tokens(chunks: list[dict[str, Any]], threshold: float = 0.6) -> set[str]:
    """
    Words that appear in most chunks (like "accommodation", "located",
    "facilities" — all from this feature's fixed template wording) carry
    no discriminating signal for keyword-overlap scoring, and worse, they
    guarantee a false overlap match for any query that happens to use
    them too (e.g. "What accommodation are in Tokyo?"). Detected
    dynamically from the actual corpus rather than hardcoded, so this
    keeps working once other students' chunks (different template
    wording) are added to the shared corpus.
    """
    doc_count = len(chunks)
    if doc_count == 0:
        return set()

    doc_frequency: dict[str, int] = {}
    for chunk in chunks:
        for token in _tokenize(chunk.get("text", "")):
            doc_frequency[token] = doc_frequency.get(token, 0) + 1

    return {token for token, count in doc_frequency.items() if count / doc_count >= threshold}




def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===================== EMBEDDING (deterministic, offline) =====================

def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        values = [0.0] * EMBED_VECTOR_SIZE
        tokens = (text or "").lower().split()

        if not tokens:
            vectors.append(values)
            continue

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i, byte in enumerate(digest):
                idx = i % EMBED_VECTOR_SIZE
                values[idx] += (byte / 255.0) - 0.5

        norm = sum(v * v for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        vectors.append(values)

    return vectors


# ===================== CHROMADB =====================

def get_collection():
    # Deliberately NOT cached globally: this pipeline can be used from
    # multiple separate processes (rag_http_server.py, terminal tests,
    # rag_server.py) that all point at the same on-disk ./chroma store.
    # Caching the collection object risks a stale reference if another
    # process calls reset_collection() (which deletes + recreates with a
    # new internal ID) after this process already cached the old one.
    # Fetching fresh each call is cheap enough for local/dev use.
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return chroma_client.get_or_create_collection(name=COLLECTION_NAME)


def reset_collection() -> None:
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        chroma_client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass
    chroma_client.get_or_create_collection(name=COLLECTION_NAME)


# ===================== AUDIT LOG =====================

def append_audit(tool_name, tool_input, tool_output, validation_status, outcome, start_time):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "request_id": str(uuid.uuid4()),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_output": tool_output,
        "timestamp": now_iso(),
        "duration_ms": int((time.time() - start_time) * 1000),
        "validation_status": validation_status,
        "outcome": outcome,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


# ===================== CORPUS =====================

def build_corpus() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    chunks.extend(load_accommodation_chunks())
    # Other students: extend chunks with your own loader's output here, e.g.
    # chunks.extend(load_flight_chunks())
    for chunk in chunks:
        chunk.setdefault("indexed_at", now_iso())
    return chunks


def write_corpus(chunks: list[dict[str, Any]]) -> None:
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")


def read_corpus() -> list[dict[str, Any]]:
    if not CORPUS_PATH.exists():
        return []
    chunks = []
    with CORPUS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return chunks


def refresh_corpus(caller: str = "student") -> dict[str, Any]:
    start = time.time()
    try:
        chunks = build_corpus()
        write_corpus(chunks)

        vector_store_status = "ready"
        vector_store_error = None
        try:
            reset_collection()
            collection = get_collection()
            if chunks:
                ids = [c["chunk_id"] for c in chunks]
                docs = [c["text"] for c in chunks]
                metas = [
                    {
                        "source_id": c["source_id"],
                        "authority_tier": c["authority_tier"],
                        "indexed_at": c["indexed_at"],
                    }
                    for c in chunks
                ]
                embeddings = embed_texts(docs)
                collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        except Exception as exc:
            vector_store_status = "degraded"
            vector_store_error = str(exc)

        output = {
            "status": "success",
            "caller": caller,
            "chunk_count": len(chunks),
            "collection": COLLECTION_NAME,
            "corpus_path": str(CORPUS_PATH),
            "vector_store_status": vector_store_status,
        }
        if vector_store_error:
            output["vector_store_error"] = vector_store_error

        append_audit("refresh_corpus", {"caller": caller}, output, "pass", "corpus_refreshed", start)
        return output
    except Exception as exc:
        output = {"status": "error", "error": str(exc)}
        append_audit("refresh_corpus", {"caller": caller}, output, "fail", "error", start)
        return output


# ===================== RETRIEVE =====================

def retrieve_context(query: str, k: int = 5, caller: str = "student") -> dict[str, Any]:
    start = time.time()
    try:
        collection = get_collection()
        if collection.count() == 0:
            refreshed = refresh_corpus(caller="auto_refresh")
            if refreshed.get("status") != "success":
                output = {"status": "error", "error": "corpus_unavailable", "query": query}
                append_audit("retrieve_context", {"query": query, "k": k, "caller": caller}, output, "fail", "error", start)
                return output

        boilerplate = _boilerplate_tokens(read_corpus())
        query_tokens = _tokenize(query) - boilerplate
        # Retrieve the WHOLE corpus as candidates, not just top-N by raw
        # vector distance. This corpus is small (tens of chunks), and the
        # hash-embedding's distances are noisy enough that a genuinely
        # relevant chunk can be excluded from a narrower top-N pool before
        # keyword-overlap re-ranking ever gets to see it. Distance is only
        # used as a tiebreaker among equal-overlap chunks below.
        candidate_n = collection.count()
        query_embedding = embed_texts([query])
        results = collection.query(query_embeddings=query_embedding, n_results=candidate_n)

        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        candidates = []
        for i, chunk_id in enumerate(ids):
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            text = docs[i] if i < len(docs) else ""
            candidate_tokens = _tokenize(text) - boilerplate
            overlap = len(query_tokens & candidate_tokens)
            candidates.append({
                "chunk_id": chunk_id,
                "source_id": meta.get("source_id"),
                "authority_tier": meta.get("authority_tier"),
                "distance": distances[i] if i < len(distances) else None,
                "text": text,
                "keyword_overlap": overlap,
            })

        # Keyword overlap is the primary sort key: this toy hash embedding's
        # distances cluster tightly because every chunk shares the same
        # boilerplate wording, so vector distance alone is an unreliable
        # ranking signal here. Distance is kept only as a tiebreaker.
        candidates.sort(
            key=lambda r: (-r["keyword_overlap"], r["distance"] if r["distance"] is not None else 1e9)
        )

        ranked = []
        for i, cand in enumerate(candidates[:k], start=1):
            cand["rank"] = i
            ranked.append(cand)

        output = {
            "status": "success",
            "query": query,
            "caller": caller,
            "k": k,
            "results": ranked,
        }
        append_audit(
            "retrieve_context",
            {"query": query, "k": k, "caller": caller},
            {"result_count": len(ranked), "chunk_ids": [r["chunk_id"] for r in ranked]},
            "pass", "context_retrieved", start,
        )
        return output
    except Exception as exc:
        output = {"status": "error", "error": str(exc), "query": query}
        append_audit("retrieve_context", {"query": query, "k": k, "caller": caller}, output, "fail", "error", start)
        return output


# ===================== ANSWER (grounded, with citations + confidence) =====================

# Confidence is based on keyword overlap between the query and the top
# retrieved chunk, not raw vector distance — this toy hash embedding's
# distances don't spread out meaningfully for short, similarly-worded
# chunks (see retrieve_context), so overlap is the trustworthy signal.

def confidence_from_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "Insufficient"

    top_overlap = results[0].get("keyword_overlap", 0)
    if top_overlap >= 2:
        return "High"
    if top_overlap == 1:
        return "Medium"
    return "Insufficient"


def generate_grounded_answer(query: str, context: str) -> str:
    prompt = (
        "Here is retrieved CONTEXT, made up of one or more separate "
        "accommodation entries. Only use facts present in it — do not "
        "invent, estimate, or assume anything not stated here. If the "
        "context does not contain enough information to answer, reply "
        "with exactly: Insufficient context.\n\n"
        "IMPORTANT: Each accommodation entry has its OWN Facilities list. "
        "Before stating that a specific accommodation has a facility "
        "(e.g. breakfast, pool, parking, wifi), check that facility is "
        "literally listed in THAT accommodation's own Facilities line. "
        "Do not assume every accommodation shares a facility just because "
        "one of them does, or because the question mentioned it. If an "
        "accommodation's Facilities line does not list something, say it "
        "does not have that facility rather than omitting or guessing.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION:\n{query}\n\n"
        "Answer in 2-3 sentences, using only the facts given above, "
        "verified per accommodation as instructed."
    )
    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a retrieval-grounded travel assistant. You only "
                        "restate and lightly rephrase facts present in the given "
                        "context. You never invent statistics or details not "
                        "present in the context. When multiple accommodations are "
                        "in the context, you check each one's own Facilities line "
                        "individually rather than assuming they all share a "
                        "facility. If the context is insufficient, you reply with "
                        "exactly: Insufficient context."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as exc:
        return f"Ollama unavailable: {exc}"


def answer_question(query: str, k: int = 5, caller: str = "student") -> dict[str, Any]:
    start = time.time()
    retrieval = retrieve_context(query=query, k=k, caller=caller)
    if retrieval.get("status") != "success":
        output = {"status": "error", "query": query, "error": retrieval.get("error", "retrieval_failed")}
        append_audit("answer_question", {"query": query, "k": k, "caller": caller}, output, "fail", "retrieval_failed", start)
        return output

    results = retrieval.get("results", [])
    confidence = confidence_from_results(results)

    if not results or confidence == "Insufficient":
        output = {
            "status": "insufficient_context",
            "query": query,
            "answer": "Insufficient context available to answer this question.",
            "citations": [],
            "confidence_category": "Insufficient",
            "retrieval_summary": {"k": k, "retrieved_count": len(results)},
        }
        append_audit("answer_question", {"query": query, "k": k, "caller": caller}, output, "pass", "insufficient_context", start)
        return output

    context = "\n\n".join(r.get("text", "") for r in results)
    answer = generate_grounded_answer(query, context)

    citations = [
        {"chunk_id": r.get("chunk_id"), "source_id": r.get("source_id"), "authority_tier": r.get("authority_tier")}
        for r in results
    ]

    output = {
        "status": "success",
        "query": query,
        "answer": answer,
        "citations": citations,
        "confidence_category": confidence,
        "retrieval_summary": {
            "k": k,
            "retrieved_count": len(results),
            "top_chunk": results[0].get("chunk_id") if results else None,
        },
    }
    append_audit(
        "answer_question",
        {"query": query, "k": k, "caller": caller},
        {"confidence_category": confidence, "citation_count": len(citations)},
        "pass", "answer_generated", start,
    )
    return output


if __name__ == "__main__":
    # Terminal validation (Terminal B):
    # cd ai-services/rag-server
    # python -c "from rag_pipeline import *; import json; print(json.dumps(refresh_corpus(), indent=2))"
    print(json.dumps(refresh_corpus(), indent=2))
    print(json.dumps(retrieve_context("pool villa in Bali", 5), indent=2))
    print(json.dumps(answer_question("What accommodations are available in Kyoto?", 5), indent=2))