"""
Builds the prompt text sent to the LLM for RAG validation mode, given the
evidence collected by itinerary_rag_collector.collect().

Same two-stage shape as itinerary_mcp_pipeline.py: an implementation pass
that reads the evidence and renders a short verdict, then a review pass
that critiques that verdict against the same evidence.
"""


def build_implementation_prompt(task_prompt: str, evidence: str) -> str:
    return f"""
{task_prompt}

Review Scope:
Itinerary / Travel App RAG Integration

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