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


# One model per role. Override any of them with PLANNER_MODEL / WORKER_MODEL / REVIEWER_MODEL.
DEFAULT_MODELS = {
    "planner": "qwen2.5:0.5b",
    "worker": "qwen2.5:0.5b",
    "reviewer": "llama3.1:8b",
}


# The Reviewer reads the longest prompt, so it gets a longer default wait.
# Override with PLANNER_TIMEOUT_SECONDS / WORKER_TIMEOUT_SECONDS / REVIEWER_TIMEOUT_SECONDS.
DEFAULT_TIMEOUTS = {"reviewer": 300.0}


def timeout_for(agent):
    value = os.environ.get(f"{agent.upper()}_TIMEOUT_SECONDS")
    return float(value) if value else DEFAULT_TIMEOUTS.get(agent)


def model_for(agent):
    return os.environ.get(f"{agent.upper()}_MODEL") or DEFAULT_MODELS.get(agent) or os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")


ECHO_MARKERS = ("Evidence (", "Evidence items available", "Request:", "Plan:", "Worker output:", "Automated checks:")


def echo_problem(output):
    """Small models sometimes repeat the prompt instead of answering; treat that as a failed step."""
    for marker in ECHO_MARKERS:
        if marker in output:
            return f"the model repeated the prompt instead of answering ('{marker}')"
    return None


def format_problem(output, required):
    """A reply must contain at least one of the required labels (case-insensitive)."""
    if required and not any(label.lower() in output.lower() for label in required):
        return "the reply did not follow the required format (expected " + " or ".join(required) + ")"
    return None


def run_agent(agent, user_prompt, fallback_text, required=()):
    model = model_for(agent)
    started = time.monotonic()
    error = None
    try:
        output = llm.chat(load_prompt(agent), user_prompt, model=model, timeout=timeout_for(agent))
        if not output:
            raise llm.LLMError("empty response")
        problem = echo_problem(output) or format_problem(output, required)
        if problem:
            raise llm.LLMError(problem)
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