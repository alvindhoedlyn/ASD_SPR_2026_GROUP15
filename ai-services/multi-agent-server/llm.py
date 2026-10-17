"""Thin client for the local Ollama OpenAI-compatible API.

Uses plain `requests` so the server has no extra SDK dependency.
Any failure is raised as LLMError so an agent can fall back safely.
"""
import os

import requests

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
STEP_TIMEOUT_SECONDS = float(os.environ.get("AGENT_STEP_TIMEOUT_SECONDS", "60"))


class LLMError(Exception):
    """The local model could not produce a usable answer."""


def chat(system_prompt, user_prompt, model=None, timeout=None):
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout or STEP_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError(str(exc)) from exc