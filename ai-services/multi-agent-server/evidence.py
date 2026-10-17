"""Helpers for the application evidence that a feature backend supplies.

The backend sends evidence (for example the result of an MCP tool call).
It can be a list of records, one record, or the {"tool", "input", "result"}
wrapper the backend's MCP routes return. Everything is normalised to a list.
"""
import json

MAX_ITEMS = 10
MAX_CHARS = 6000
_LABEL_KEYS = ("name", "title", "accommodation_name")


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
        if key in _LABEL_KEYS or len(parts) >= 4:
            continue
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, list) and value and all(isinstance(v, (str, int, float)) for v in value):
            parts.append(f"{key}: {', '.join(str(v) for v in value[:5])}")
    return f"{name} ({'; '.join(parts)})" if parts else name