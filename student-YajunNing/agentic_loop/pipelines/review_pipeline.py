"""Build concise, evidence-grounded prompts for all Release 2 review modes."""


def build_implementation_prompt(task_prompt, evidence):
    return f"""
{task_prompt}

Observed evidence:
{evidence}

Reply in at most 100 words. Give a PASS/FAIL recommendation and do not invent evidence.
""".strip()


def build_review_prompt(implementation_output, evidence):
    return f"""
Implementation recommendation:
{implementation_output}

Observed evidence:
{evidence}

Reply in at most 60 words. Check the recommendation against the evidence and identify any missing proof.
""".strip()
