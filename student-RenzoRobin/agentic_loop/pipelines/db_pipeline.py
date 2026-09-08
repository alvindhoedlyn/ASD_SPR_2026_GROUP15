def build_implementation_prompt(task_prompt: str, evidence: str) -> str:
    task_with_evidence = task_prompt.replace("{{REVIEW_TARGET}}", "Database")
    task_with_evidence = task_with_evidence.replace("{{VALIDATION_EVIDENCE}}", evidence)
    return task_with_evidence.strip()


def build_review_prompt(implementation_output: str, evidence: str) -> str:
    return f"""
Implementation Recommendation:
{implementation_output}

Observed Evidence:
{evidence}

Reply in at most 35 words and stay evidence-based.
""".strip()