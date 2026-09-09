def build_implementation_prompt(
    task_prompt,
    evidence
):
    return f"""
{task_prompt}

Observed Evidence:
{evidence}

Use only the evidence shown above.
Do not invent missing information.
Give one clear improvement.
Keep the response under 80 words.
""".strip()


def build_review_prompt(
    implementation_output,
    evidence
):
    return f"""
Implementation Agent Response:
{implementation_output}

Observed Evidence:
{evidence}

Review the response against the evidence.

If it is correct, explain why it is supported.
If it is incorrect, identify the problem and provide a correction.

Do not invent information.
Keep the response under 60 words.
""".strip()