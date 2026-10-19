"""Build prompts for the Student 4 testing-report review."""

SCOPE = (
    "Location Recommender pre-commit security "
    "and post-commit endpoint testing"
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

Reply in at most 100 words.
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
Reply in at most 60 words.
Remain evidence-based.
""".strip()