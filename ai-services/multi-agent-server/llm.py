"""Thin client for the local Ollama OpenAI-compatible API.

Uses plain `requests` so the server has no extra SDK dependency.
Any failure is raised as LLMError so an agent can fall back safely.

Reasoning models (for example deepseek-r1) write their thinking in a
<think>...</think> block before the answer. That block is removed here, and
these models get a larger token budget and a longer timeout so the thinking
does not use up the whole reply before the answer starts.
"""
import os
import re

import requests

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
STEP_TIMEOUT_SECONDS = float(os.environ.get("AGENT_STEP_TIMEOUT_SECONDS", "120"))
# Caps each agent reply so a small model cannot ramble or loop until the timeout.
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "300"))

REASONING_MODELS = tuple(
    m.strip().lower() for m in os.environ.get("REASONING_MODELS", "deepseek-r1,qwq").split(",") if m.strip()
)
REASONING_MAX_TOKENS = int(os.environ.get("REASONING_MAX_TOKENS", "2500"))
REASONING_TIMEOUT_SECONDS = float(os.environ.get("REASONING_TIMEOUT_SECONDS", "300"))

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LLMError(Exception):
    """The local model could not produce a usable answer."""


def is_reasoning_model(model):
    return any(name in (model or "").lower() for name in REASONING_MODELS)


def clean_reply(text):
    """Remove the reasoning block; an unfinished one means the model never reached its answer."""
    text = _THINK_BLOCK.sub("", text).strip()
    if "<think>" in text.lower():
        raise LLMError("the reasoning model ran out of tokens before it gave an answer")
    return text


def chat(system_prompt, user_prompt, model=None, timeout=None):
    model = model or DEFAULT_MODEL
    reasoning = is_reasoning_model(model)
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": REASONING_MAX_TOKENS if reasoning else MAX_TOKENS,
        "stream": False,
    }
    wait = timeout or (REASONING_TIMEOUT_SECONDS if reasoning else STEP_TIMEOUT_SECONDS)
    try:
        response = requests.post(url, json=payload, timeout=wait)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError(str(exc)) from exc
    return clean_reply(content or "")