"""
JourneyBuddy Shared Local RAG Server.

This server runs locally and is NOT containerised.

It:
1. Loads approved project knowledge.
2. Retrieves relevant knowledge chunks.
3. Calculates a confidence category.
4. Uses a local Ollama LLM to generate a grounded response.
5. Returns source citations and retrieved context.
6. Returns an insufficient-context response when appropriate.

Run:
    cd ai-services/rag-server
    python server.py

Endpoint:
    POST http://localhost:8100/query
"""

from pathlib import Path
import json
import os
import re
import urllib.error
import urllib.request

from flask import Flask, jsonify, request


# =========================================================
# Configuration
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

HOST = "0.0.0.0"
PORT = 8100

# Shared RAG runs locally, so it talks directly to the
# non-containerised Ollama service running on the host.
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:0.5b",
)

app = Flask(__name__)


# =========================================================
# Knowledge Loading
# =========================================================

def load_knowledge_documents():
    """
    Load approved Markdown and text files from the
    local knowledge directory.
    """

    documents = []

    if not KNOWLEDGE_DIR.exists():
        return documents

    supported_extensions = {
        ".md",
        ".txt",
    }

    for file_path in sorted(KNOWLEDGE_DIR.iterdir()):

        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in supported_extensions:
            continue

        content = file_path.read_text(
            encoding="utf-8"
        )

        documents.append({
            "source": file_path.name,
            "content": content,
        })

    return documents


# =========================================================
# Text Processing
# =========================================================

def normalise_text(text):
    """
    Convert text into a simple searchable representation.
    """

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def tokenise(text):
    """
    Convert text into useful search tokens.
    """

    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "with",
    }

    words = normalise_text(text).split()

    return {
        word
        for word in words
        if len(word) > 1
        and word not in stop_words
    }


# =========================================================
# Chunking
# =========================================================

def split_document_into_chunks(document):
    """
    Split a knowledge document into small sections.

    Markdown headings are kept with their section content
    so retrieved passages remain understandable.
    """

    source = document["source"]
    content = document["content"]

    chunks = []

    current_heading = ""
    current_lines = []

    def save_chunk():
        if not current_lines:
            return

        body = "\n".join(
            current_lines
        ).strip()

        if not body:
            return

        if current_heading:
            text = (
                f"{current_heading}\n\n"
                f"{body}"
            )
        else:
            text = body

        chunks.append({
            "source": source,
            "heading": current_heading,
            "text": text,
        })

    for line in content.splitlines():

        stripped = line.strip()

        if stripped.startswith("#"):

            save_chunk()

            current_heading = stripped.lstrip(
                "#"
            ).strip()

            current_lines = []

        else:
            current_lines.append(line)

    save_chunk()

    return chunks


def build_knowledge_chunks():
    """
    Load all approved documents and create searchable chunks.
    """

    documents = load_knowledge_documents()

    chunks = []

    for document in documents:
        chunks.extend(
            split_document_into_chunks(
                document
            )
        )

    return chunks


# =========================================================
# Retrieval
# =========================================================

def calculate_relevance(question, chunk):
    """
    Calculate relevance between a question and a knowledge chunk.

    Ranking considers:
    1. Question keywords found in the chunk.
    2. Extra weight when keywords appear in the section heading.
    3. Extra weight when the heading closely matches the question.
    """

    question_tokens = tokenise(question)
    chunk_tokens = tokenise(chunk["text"])

    heading_tokens = tokenise(
        chunk.get(
            "heading",
            "",
        )
    )

    if not question_tokens:
        return 0.0

    matched_tokens = (
        question_tokens
        & chunk_tokens
    )

    if not matched_tokens:
        return 0.0

    content_score = (
        len(matched_tokens)
        / len(question_tokens)
    )

    heading_matches = (
        question_tokens
        & heading_tokens
    )

    heading_score = (
        len(heading_matches)
        / len(question_tokens)
    )

    if heading_tokens:
        heading_coverage = (
            len(
                question_tokens
                & heading_tokens
            )
            / len(heading_tokens)
        )
    else:
        heading_coverage = 0.0

    score = (
        content_score
        + (0.5 * heading_score)
        + (0.5 * heading_coverage)
    )

    return round(
        score,
        4,
    )


def retrieve_context(question, limit=3):
    """
    Retrieve the most relevant approved knowledge chunks.
    """

    chunks = build_knowledge_chunks()

    scored_chunks = []

    for chunk in chunks:

        score = calculate_relevance(
            question,
            chunk,
        )

        if score <= 0:
            continue

        result = dict(chunk)
        result["score"] = score

        scored_chunks.append(
            result
        )

    scored_chunks.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return scored_chunks[:limit]


# =========================================================
# Confidence
# =========================================================

def determine_confidence(score):
    """
    Convert retrieval relevance into a confidence category.
    """

    if score >= 0.75:
        return "high"

    if score >= 0.45:
        return "medium"

    if score >= 0.25:
        return "low"

    return "insufficient"


# =========================================================
# Local LLM Grounded Generation
# =========================================================

def generate_grounded_answer(question, retrieved_chunks):
    """
    Generate an answer using the selected local Ollama model.

    The model is instructed to use only the retrieved
    approved project context.
    """

    context_parts = []

    for index, chunk in enumerate(
        retrieved_chunks,
        start=1,
    ):
        context_parts.append(
            (
                f"[Context {index}]\n"
                f"Source: {chunk['source']}\n"
                f"Section: {chunk['heading']}\n"
                f"{chunk['text']}"
            )
        )

    grounded_context = "\n\n".join(
        context_parts
    )

    prompt = f"""
You are the JourneyBuddy grounded RAG assistant.

Answer the user's question using ONLY the approved retrieved
project context provided below.

Rules:
- Do not use outside knowledge.
- Do not invent facts.
- Keep the answer concise and clear.
- Base every factual statement on the retrieved context.
- Do not invent source names.
- If the retrieved context does not contain enough information
  to answer the question, reply exactly:
  INSUFFICIENT_CONTEXT

User question:
{question}

Approved retrieved context:
{grounded_context}

Grounded answer:
""".strip()

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
        },
    }

    request_body = json.dumps(
        payload
    ).encode("utf-8")

    ollama_request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=request_body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            ollama_request,
            timeout=120,
        ) as response:

            response_data = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            "Local Ollama returned HTTP "
            f"{error.code}: {error_body}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            "Unable to connect to local Ollama at "
            f"{OLLAMA_BASE_URL}: {error.reason}"
        ) from error

    answer = str(
        response_data.get(
            "response",
            "",
        )
    ).strip()

    if not answer:
        raise RuntimeError(
            "Local Ollama returned an empty response."
        )

    return answer


def extract_flight_facts(retrieved_chunks):
    """Extract stable, checkable flight facts from approved Flight knowledge."""

    facts = []
    seen_numbers = set()
    pattern = re.compile(
        r"(?P<airline>[A-Za-z][A-Za-z ]*?) flight "
        r"(?P<number>[A-Z]{1,3}[0-9]{1,4}) travels from "
        r"(?P<origin_city>.+?) \((?P<origin>[A-Z]{3})\) to "
        r"(?P<destination_city>.+?) \((?P<destination>[A-Z]{3})\)\. "
        r"It departs at (?P<departure>[0-9:]+), arrives at "
        r"(?P<arrival>[0-9:]+), costs AUD (?P<price>[0-9.]+), "
        r"takes (?P<duration>[0-9]+) minutes, and has "
        r"(?P<stops>zero|[0-9]+) stops?\.",
        re.IGNORECASE,
    )

    for chunk in retrieved_chunks:
        compact_text = re.sub(r"\s+", " ", chunk.get("text", "")).strip()
        for match in pattern.finditer(compact_text):
            fact = match.groupdict()
            number = fact["number"].upper()
            if number in seen_numbers:
                continue
            seen_numbers.add(number)
            fact["number"] = number
            fact["airline"] = fact["airline"].strip()
            fact["price"] = float(fact["price"])
            fact["duration"] = int(fact["duration"])
            fact["stops"] = 0 if fact["stops"].lower() == "zero" else int(fact["stops"])
            fact["chunk"] = chunk
            facts.append(fact)

    return facts


def select_flight_facts(question, facts):
    """Apply explicit user constraints to retrieved Flight facts."""

    lowered = question.lower()
    selected = list(facts)
    requested_numbers = set(re.findall(r"\b[A-Z]{1,3}[0-9]{1,4}\b", question.upper()))
    budget_match = re.search(
        r"(?:under|below|less than|no more than|within)\s+"
        r"(?:aud\s*)?\$?\s*([0-9]+(?:\.[0-9]+)?)",
        lowered,
    )

    if requested_numbers:
        selected = [fact for fact in selected if fact["number"] in requested_numbers]
    if "direct" in lowered or "nonstop" in lowered or "non-stop" in lowered:
        selected = [fact for fact in selected if fact["stops"] == 0]
    if budget_match:
        maximum_price = float(budget_match.group(1))
        selected = [fact for fact in selected if fact["price"] < maximum_price]
    if "cheapest" in lowered and selected:
        cheapest_price = min(fact["price"] for fact in selected)
        selected = [fact for fact in selected if fact["price"] == cheapest_price]

    return sorted(selected, key=lambda fact: (fact["price"], fact["duration"]))


def flight_answer_is_grounded(answer, selected_facts):
    """Reject model output that names a flight outside the validated result set."""

    if not selected_facts or not answer:
        return False
    mentioned_numbers = set(re.findall(r"\b[A-Z]{1,3}[0-9]{1,4}\b", answer.upper()))
    valid_numbers = {fact["number"] for fact in selected_facts}
    if not mentioned_numbers or not mentioned_numbers.issubset(valid_numbers):
        return False
    return all(
        str(int(fact["price"])) in answer
        for fact in selected_facts
        if fact["number"] in mentioned_numbers
    )


def deterministic_flight_answer(selected_facts):
    """Build a safe fallback exclusively from parsed approved Flight facts."""

    summaries = []
    for fact in selected_facts[:3]:
        stop_label = "direct" if fact["stops"] == 0 else f"has {fact['stops']} stop(s)"
        summaries.append(
            f"{fact['airline']} {fact['number']} is {stop_label}, travels from "
            f"{fact['origin']} to {fact['destination']}, and costs AUD {fact['price']:.0f}"
        )
    return "Based on the approved Flight catalogue, " + "; ".join(summaries) + "."


# =========================================================
# Grounded Answer Construction
# =========================================================

def build_answer(question, retrieved_chunks):
    """
    Validate retrieved context and generate a grounded
    response using the selected local LLM.
    """

    if not retrieved_chunks:

        return {
            "answer": (
                "Insufficient context: the approved "
                "JourneyBuddy knowledge base does not "
                "contain enough information to answer "
                "this question reliably."
            ),
            "sources": [],
            "confidence": "insufficient",
            "retrieved_context": [],
            "model": None,
        }

    best_score = retrieved_chunks[0][
        "score"
    ]

    confidence = determine_confidence(
        best_score
    )

    if confidence == "insufficient":

        return {
            "answer": (
                "Insufficient context: the retrieved "
                "knowledge is not relevant enough to "
                "answer this question reliably."
            ),
            "sources": [],
            "confidence": "insufficient",
            "retrieved_context": retrieved_chunks,
            "model": None,
        }

    sources = []

    for chunk in retrieved_chunks:

        citation = {
            "document": chunk[
                "source"
            ],
            "section": chunk[
                "heading"
            ],
        }

        if citation not in sources:
            sources.append(
                citation
            )

    answer = generate_grounded_answer(
        question,
        retrieved_chunks,
    )

    generation_mode = "local_llm"
    flight_chunks = [
        chunk for chunk in retrieved_chunks
        if chunk.get("source") == "flights.md"
    ]
    selected_facts = select_flight_facts(
        question,
        extract_flight_facts(flight_chunks),
    )
    has_flight_constraints = bool(
        re.search(
            r"\b(flight|direct|nonstop|non-stop|cheapest|under|below|less than)\b",
            question,
            re.IGNORECASE,
        )
    )

    if flight_chunks and has_flight_constraints:
        if not selected_facts:
            return {
                "answer": (
                    "Insufficient context: no flight in the approved catalogue "
                    "satisfies the requested constraints."
                ),
                "sources": [],
                "confidence": "insufficient",
                "retrieved_context": retrieved_chunks,
                "model": OLLAMA_MODEL,
                "generation_mode": "validated_fallback",
            }
        if not flight_answer_is_grounded(answer, selected_facts):
            answer = deterministic_flight_answer(selected_facts)
            generation_mode = "validated_fallback"
            selected_numbers = {fact["number"] for fact in selected_facts}
            retrieved_chunks = [
                chunk for chunk in flight_chunks
                if any(number in chunk.get("text", "") for number in selected_numbers)
            ]
            sources = []
            for chunk in retrieved_chunks:
                citation = {
                    "document": chunk["source"],
                    "section": chunk["heading"],
                }
                if citation not in sources:
                    sources.append(citation)

    if answer.strip().upper() == "INSUFFICIENT_CONTEXT":

        return {
            "answer": (
                "Insufficient context: the approved "
                "JourneyBuddy knowledge base does not "
                "contain enough information to answer "
                "this question reliably."
            ),
            "sources": [],
            "confidence": "insufficient",
            "retrieved_context": retrieved_chunks,
            "model": OLLAMA_MODEL,
            "generation_mode": generation_mode,
        }

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "retrieved_context": retrieved_chunks,
        "model": OLLAMA_MODEL,
        "generation_mode": generation_mode,
    }


# =========================================================
# Health Endpoint
# =========================================================

@app.route(
    "/health",
    methods=["GET"],
)
def health():
    """
    Check whether the shared RAG server is running.
    """

    documents = load_knowledge_documents()
    chunks = build_knowledge_chunks()

    return jsonify({
        "status": "ok",
        "service": "journeybuddy-shared-rag",
        "knowledge_documents": len(
            documents
        ),
        "knowledge_chunks": len(
            chunks
        ),
        "ollama_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
    })


# =========================================================
# RAG Query Endpoint
# =========================================================

@app.route(
    "/query",
    methods=["POST"],
)
def query_rag():
    """
    Retrieve approved JourneyBuddy knowledge and generate
    a grounded response using the selected local LLM.
    """

    data = request.get_json(
        silent=True
    ) or {}

    question = str(
        data.get(
            "question",
            "",
        )
    ).strip()

    if not question:

        return jsonify({
            "error": "Question is required"
        }), 400

    retrieved_chunks = retrieve_context(
        question
    )

    try:
        result = build_answer(
            question,
            retrieved_chunks,
        )

    except RuntimeError as error:

        return jsonify({
            "error": str(error),
            "service": "journeybuddy-shared-rag",
            "model": OLLAMA_MODEL,
        }), 503

    return jsonify({
        "question": question,
        "answer": result[
            "answer"
        ],
        "sources": result[
            "sources"
        ],
        "confidence": result[
            "confidence"
        ],
        "retrieved_context": result[
            "retrieved_context"
        ],
        "model": result[
            "model"
        ],
        "generation_mode": result.get(
            "generation_mode",
            "not_applicable",
        ),
        "service": "journeybuddy-shared-rag",
    }), 200


# =========================================================
# Error Handlers
# =========================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "error": "RAG endpoint not found"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({
        "error": "Method not allowed"
    }), 405


# =========================================================
# Application Start
# =========================================================

if __name__ == "__main__":

    documents = load_knowledge_documents()
    chunks = build_knowledge_chunks()

    print(
        "Starting JourneyBuddy Shared RAG Server..."
    )

    print(
        f"Knowledge directory: {KNOWLEDGE_DIR}"
    )

    print(
        f"Knowledge documents: {len(documents)}"
    )

    print(
        f"Knowledge chunks: {len(chunks)}"
    )

    print(
        f"Local Ollama: {OLLAMA_BASE_URL}"
    )

    print(
        f"Grounded-response model: {OLLAMA_MODEL}"
    )

    print(
        "RAG endpoint: http://localhost:8100/query"
    )

    app.run(
        host=HOST,
        port=PORT,
        debug=False,
    )
