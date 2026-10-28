"""Security pipeline: prompt builders for the security mode of the agentic loop.

Same contract as mcp_pipeline / rag_pipeline / multi_agent_pipeline:
  build_implementation_prompt(task_prompt, evidence) -> str   (first-pass model, qwen)
  build_review_prompt(implementation_output, evidence) -> str (second-pass model)

Both models are small and local, so the evidence is capped and the reply length
is stated explicitly.
"""

# Five checks, each with findings, must all fit: a cut-off would drop the last (post-commit)
# results. ~3000 characters is roughly 800 tokens, which still fits a small local model's context.
MAX_EVIDENCE_CHARS = 3000


def _trim(evidence):
    if len(evidence) <= MAX_EVIDENCE_CHARS:
        return evidence
    return evidence[:MAX_EVIDENCE_CHARS] + "\n...[evidence truncated]"


def build_implementation_prompt(task_prompt, evidence):
    return (
        f"{task_prompt}\n\n"
        "Review Scope:\n"
        "- Only the security check results below. Nothing else about the application.\n\n"
        f"Observed Evidence:\n{_trim(evidence)}\n\n"
        "Reply with at most two short bullet points, under 60 words in total."
    )


def build_review_prompt(implementation_output, evidence):
    return (
        "You are the second-pass reviewer of a security check summary.\n\n"
        f"Observed Evidence:\n{_trim(evidence)}\n\n"
        f"First reviewer's answer:\n{implementation_output}\n\n"
        "Task:\n"
        "- Keep only points that the evidence directly supports "
        "(a FAIL, ERROR, NOT RUN, WARNING or KNOWN GAP line).\n"
        "- Remove any invented file, package, CVE or secret value.\n"
        "- If every check passed, there is no KNOWN GAP line, and the answer claims a problem, reply: "
        "'No evidence-backed improvement identified.'\n"
        "- If the answer is correct, reply 'Confirmed.' followed by its bullets.\n"
        "Reply in under 50 words."
    )