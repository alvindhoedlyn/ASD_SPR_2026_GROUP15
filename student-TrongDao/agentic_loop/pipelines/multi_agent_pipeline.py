"""Build prompts for the Student 4 Multi-Agent workflow review."""

SCOPE = (
    "Location Recommender Planner, Worker, Reviewer, "
    "and Human Review workflow"
)


def build_implementation_prompt(
    task_prompt,
    evidence
):
    return f"""
{task_prompt}

Review Scope:
{SCOPE}

Observed Evidence:
{evidence}

Reply in at most 110 words.
Remain evidence-based.
""".strip()


def build_review_prompt(
    implementation_output,
    evidence
):
    return f"""
Implementation Recommendation:
{implementation_output}

Observed Evidence:
{evidence}

Return a final PASS, REVISE, or FAIL decision.
Pay particular attention to the reviewer and human decisions.
Reply in at most 70 words.
Remain evidence-based.
""".strip()
