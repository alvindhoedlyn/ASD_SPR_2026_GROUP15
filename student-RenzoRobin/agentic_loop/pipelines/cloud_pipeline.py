"""
Builds the prompt text sent to the LLM for this review mode, given the
evidence collected by the matching collector.
"""

SCOPE = "Accommodation Recommender Azure Cloud Deployment"


def build_implementation_prompt(task_prompt: str, evidence: str) -> str:
    return f"""
{task_prompt}

Review Scope:
{SCOPE}

Observed Evidence:
{evidence}

Reply in at most 70 words and stay evidence-based.
""".strip()


def build_review_prompt(implementation_output: str, evidence: str) -> str:
    return f"""
Implementation Recommendation:
{implementation_output}

Observed Evidence:
{evidence}

Reply in at most 40 words and stay evidence-based.
""".strip()