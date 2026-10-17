"""Reviewer agent: checks the Worker output against the plan and the evidence.

Two layers: deterministic checks (so the review does not depend only on a
small model), then the model's written review. The checks are included in
the model prompt, returned in the step as `checks`, and they decide the
verdict if the small model ignores the required format or says PASS anyway.
"""
import re

import evidence as ev
from agents.base import run_agent

_NUMBER = re.compile(r"\d+\.\d+|\d{2,}")
_VERDICT = re.compile(r"VERDICT:\s*(PASS|REVISE|FAIL)", re.IGNORECASE)
_SOURCES_LINE = re.compile(r"^\s*SOURCES:.*$", re.IGNORECASE | re.MULTILINE)
MAX_LISTED = 5
MAX_PROMPT_TEXT = 700  # keeps the prompt small so a local 8B model can answer in time


def _evidence_lines(items):
    """Only what the review needs: each record's name and its list fields (e.g. facilities)."""
    lines = []
    for item in items[:ev.MAX_ITEMS]:
        facts = ""
        if isinstance(item, dict):
            facts = "; ".join(f"{key}: {', '.join(map(str, value))}" for key, value in item.items() if isinstance(value, list) and value)
        lines.append(f"- {ev.label(item)}" + (f" | {facts}" if facts else ""))
    return "\n".join(lines)


def _coverage(user_request, worker_output, items):
    """If the request asks for a listed term (e.g. 'breakfast'), the Worker must
    name every record that has it, and must not name records that lack it.

    Returns (problems, verified): problems feed the verdict; verified are the
    terms that passed, so a human can see what was confirmed by rules.
    """
    output = _SOURCES_LINE.sub("", worker_output).lower()
    named = [i for i in items if ev.label(i) != "item" and ev.label(i).lower() in output]
    problems, verified = [], []
    for term in ev.requested_terms(user_request, items):
        matching = [i for i in items if term in ev.list_terms(i)]
        wrong = [ev.label(i) for i in named if i not in matching]
        missing = [ev.label(i) for i in matching if i not in named]
        if wrong:
            problems.append(f"The Worker named {', '.join(wrong[:MAX_LISTED])}, which does not list '{term}' in the evidence.")
        if missing:
            problems.append(
                f"The evidence has {len(matching)} item(s) listing '{term}' but the Worker named "
                f"{len(matching) - len(missing)}; not mentioned: {', '.join(missing[:MAX_LISTED])}."
            )
        if matching and not wrong and not missing:
            verified.append(
                f"All {len(matching)} item(s) listing '{term}' were named, and no named item lacks it "
                f"({', '.join(ev.label(i) for i in matching[:MAX_LISTED])})."
            )
    return problems, verified


def _checks(user_request, worker_step, items):
    checks = []
    if not items:
        checks.append("No evidence was supplied, so the Worker output cannot be verified.")
    if worker_step["status"] == "fallback":
        checks.append("The Worker used its deterministic fallback because the model was unavailable or gave an unusable answer.")
    # Only model-written answers can contain invented figures; the deterministic
    # fallback's own counts (for example "5 of 10 items") are not claims about the evidence.
    evidence_text = ev.compact(items)
    unsupported = sorted({n for n in _NUMBER.findall(worker_step["output"]) if n not in evidence_text})
    if items and unsupported and worker_step["status"] == "ok":
        checks.append("The Worker output contains figures not found in the evidence: " + ", ".join(unsupported[:5]) + ".")
    if items:
        checks.extend(_coverage(user_request, worker_step["output"], items)[0])
    return checks


def _enforce_verdict(output, checks):
    """Make sure the output carries a verdict, and that it is never PASS while checks failed."""
    verdict = "REVISE" if checks else "PASS"
    match = _VERDICT.search(output)
    if not match:
        return f"VERDICT: {verdict} (set by automated checks)\n{output}"
    if checks and match.group(1).upper() == "PASS":
        return _VERDICT.sub("VERDICT: REVISE (raised by automated checks)", output, count=1)
    return output


def run(user_request, plan_text, worker_step, items):
    checks = _checks(user_request, worker_step, items)
    check_text = "\n".join(f"- {c}" for c in checks) or "- None detected by automated checks."
    user_prompt = (
        f"Request: {user_request}\n\n"
        f"Plan:\n{plan_text[:MAX_PROMPT_TEXT]}\n\n"
        f"Worker output:\n{worker_step['output'][:MAX_PROMPT_TEXT]}\n\n"
        f"Evidence ({len(items)} item(s)):\n{_evidence_lines(items)}\n\n"
        f"Automated checks:\n{check_text}\n\n"
        "Now write only the VERDICT, RISKS and RECOMMENDATION lines. Do not repeat the evidence."
    )
    verdict = "REVISE" if checks else "PASS"
    fallback = (
        f"VERDICT: {verdict}\n"
        f"RISKS:\n{check_text}\n"
        "RECOMMENDATION: A human must approve, correct or reject this result."
    )
    step = run_agent("reviewer", user_prompt, fallback, required=("VERDICT:", "RISKS:", "RECOMMENDATION:"))
    step["output"] = _enforce_verdict(step["output"], checks)
    step["checks"] = checks
    # What the rules confirmed. Shown beside the model's text, which can be wrong.
    step["verified"] = _coverage(user_request, worker_step["output"], items)[1] if items else []
    return step