"""Shared runner for the three agents.

Each agent loads its prompt file, calls the local model, and falls back to a
deterministic answer if the model is unavailable. This keeps the workflow
finishing (and reaching human review) even when Ollama is down or slow.
"""
import os
import time
from pathlib import Path

import llm

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(agent):
    return (PROMPT_DIR / f"{agent}.txt").read_text(encoding="utf-8").strip()


def model_for(agent):
    """PLANNER_MODEL / WORKER_MODEL / REVIEWER_MODEL, else OLLAMA_MODEL."""
    return os.environ.get(f"{agent.upper()}_MODEL") or os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")


def run_agent(agent, user_prompt, fallback_text):
    model = model_for(agent)
    started = time.monotonic()
    error = None
    try:
        output = llm.chat(load_prompt(agent), user_prompt, model=model)
        if not output:
            raise llm.LLMError("empty response")
        status = "ok"
    except llm.LLMError as exc:
        output, status, error = fallback_text, "fallback", str(exc)
    step = {
        "agent": agent,
        "model": model,
        "status": status,
        "output": output,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }
    if error:
        step["error"] = error
    return step