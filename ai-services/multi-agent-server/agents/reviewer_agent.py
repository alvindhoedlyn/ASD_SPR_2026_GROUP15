"""Reviewer agent: checks the Worker output against the plan and the evidence.

Two layers: a few deterministic checks (so the review does not depend only on
a small model), then the model's written review. The checks are included in
the model prompt and returned in the step as `checks`.
"""
import re

import evidence as ev
from agents.base import run_agent

_NUMBER = re.compile(r"\d+\.\d+|\d{2,}")


def _checks(worker_step, items):
    checks = []
    if not items:
        checks.append("No evidence was supplied, so the Worker output cannot be verified.")
    if worker_step["status"] == "fallback":
        checks.append("The Worker used its deterministic fallback because the model was unavailable.")
    evidence_text = ev.compact(items)
    unsupported = sorted({n for n in _NUMBER.findall(worker_step["output"]) if n not in evidence_text})
    if items and unsupported:
        checks.append("The Worker output contains figures not found in the evidence: " + ", ".join(unsupported[:5]) + ".")
    return checks


def run(user_request, plan_text, worker_step, items):
    checks = _checks(worker_step, items)
    check_text = "\n".join(f"- {c}" for c in checks) or "- None detected by automated checks."
    user_prompt = (
        f"Request: {user_request}\n\n"
        f"Plan:\n{plan_text}\n\n"
        f"Worker output:\n{worker_step['output']}\n\n"
        f"Evidence (JSON):\n{ev.compact(items)}\n\n"
        f"Automated checks:\n{check_text}"
    )
    verdict = "REVISE" if checks else "PASS"
    fallback = (
        f"VERDICT: {verdict}\n"
        f"RISKS:\n{check_text}\n"
        "RECOMMENDATION: A human must approve, correct or reject this result."
    )
    step = run_agent("reviewer", user_prompt, fallback)
    step["checks"] = checks
    return step