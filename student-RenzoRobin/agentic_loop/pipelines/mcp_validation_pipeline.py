"""
Builds the prompt text sent to the LLM for MCP validation mode, given the
evidence collected by mcp_collector.collect().
"""


def build_implementation_prompt(task_prompt: str, evidence: str) -> str:
    return f"""
{task_prompt}

Review Scope:
Accommodation Recommender MCP Integration

Observed Evidence:
{evidence}

Reply in at most 60 words and stay evidence-based.
""".strip()


def build_review_prompt(implementation_output: str, evidence: str) -> str:
    return f"""
Implementation Recommendation:
{implementation_output}

Observed Evidence:
{evidence}

Reply in at most 35 words and stay evidence-based.
""".strip()