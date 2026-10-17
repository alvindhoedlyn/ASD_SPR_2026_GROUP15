"""Planner agent: turns the request into a short plan and names the evidence needed."""
from agents.base import run_agent


def run(user_request, feature, evidence_count):
    user_prompt = (
        f"Feature: {feature}\n"
        f"Request: {user_request}\n"
        f"Evidence items available: {evidence_count}"
    )
    fallback = (
        f"GOAL: {user_request}\n"
        "STEPS:\n"
        f"1. Review the supplied {feature} evidence.\n"
        "2. Answer using only that evidence.\n"
        "3. Flag anything the evidence does not cover.\n"
        f"EVIDENCE NEEDED: {evidence_count} item(s) supplied."
    )
    return run_agent("planner", user_prompt, fallback)