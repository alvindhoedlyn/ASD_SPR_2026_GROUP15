"""Helpers for the application evidence that a feature backend supplies.

The backend sends evidence (for example the result of an MCP tool call).
It can be a list of records, one record, or the {"tool", "input", "result"}
wrapper the backend's MCP routes return. Everything is normalised to a list.
"""
import json
import re

MAX_ITEMS = 10
MAX_CHARS = 6000
_LABEL_KEYS = ("name", "title", "accommodation_name")
# Fields that add tokens but no meaning for the agents.
_NOISE_KEYS = {"created_at", "updated_at", "images", "image", "image_url"}
_NEGATION = re.compile(r"\b(no|not|without|except|excluding|lack|lacking)\b|n't", re.IGNORECASE)


def normalize(evidence):
    if evidence is None:
        return []
    if isinstance(evidence, dict) and "result" in evidence:
        evidence = evidence["result"]
    if isinstance(evidence, dict):
        # A tool that could not reach its data returns {"error": ...}: no evidence.
        if set(evidence) <= {"error", "detail"}:
            return []
        return [evidence]
    if isinstance(evidence, list):
        return [item for item in evidence if item not in (None, "", {})]
    return [evidence]


def compact(items):
    """Compact JSON of the evidence, capped so a small model can read it."""
    return json.dumps(items[:MAX_ITEMS], default=str, ensure_ascii=False)[:MAX_CHARS]


def brief(items):
    """Short one-line-per-record text for agent prompts (much smaller than the JSON)."""
    lines = []
    for item in items[:MAX_ITEMS]:
        if not isinstance(item, dict):
            lines.append(str(item)[:200])
            continue
        parts = []
        for key, value in item.items():
            if key in _LABEL_KEYS or key in _NOISE_KEYS or value in (None, "", [], {}):
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            parts.append(f"{key}: {value}")
        lines.append(f"- {label(item)} | " + "; ".join(parts))
    return "\n".join(lines)[:MAX_CHARS]


def list_terms(item):
    """Every string found in a list-valued field of a record (e.g. facilities)."""
    if not isinstance(item, dict):
        return set()
    return {v for value in item.values() if isinstance(value, list) for v in value if isinstance(v, str)}


def requested_terms(user_request, items):
    """List-field terms (e.g. 'breakfast') that the request asks for.

    Negated requests ("which do not include breakfast") return [] because
    the checks built on this only handle positive requests.
    """
    if _NEGATION.search(user_request or ""):
        return []
    terms = sorted({t for item in items for t in list_terms(item)})
    return [t for t in terms if re.search(rf"\b{re.escape(t)}\b", user_request or "", re.IGNORECASE)]


def label(item):
    if isinstance(item, dict):
        for key in _LABEL_KEYS:
            if item.get(key):
                return str(item[key])
        if item.get("id") is not None:
            return f"id {item['id']}"
    return "item"


def describe(item):
    """One short, deterministic line describing a record."""
    if not isinstance(item, dict):
        return str(item)[:120]
    name = label(item)
    parts = []
    for key, value in item.items():
        if key in _LABEL_KEYS or key in _NOISE_KEYS or key == "id" or key.endswith("_id") or len(parts) >= 4:
            continue
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, list) and value and all(isinstance(v, (str, int, float)) for v in value):
            parts.append(f"{key}: {', '.join(str(v) for v in value[:5])}")
    return f"{name} ({'; '.join(parts)})" if parts else name