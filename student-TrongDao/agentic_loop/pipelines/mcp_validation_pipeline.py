"""Build evidence-constrained prompts for MCP validation mode."""


def build_implementation_prompt(task_prompt, evidence):
    return f"""
{task_prompt}

Review Scope:
Attraction Recommender MCP Integration

Observed Evidence:
{evidence}

Use only the observed evidence.
Keep the response under 80 words.
""".strip()


def build_review_prompt(implementation_output, evidence):
    return f"""
Implementation Agent Response:
{implementation_output}

Observed Evidence:
{evidence}

Check the response against the evidence.
Do not invent information.
Keep the response under 60 words.
""".strip()
