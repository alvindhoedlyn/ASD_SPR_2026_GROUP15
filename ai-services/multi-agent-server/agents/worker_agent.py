"""Worker agent: carries out the plan using only the supplied evidence."""
import evidence as ev
from agents.base import run_agent


def run(user_request, plan_text, items):
    user_prompt = (
        f"Plan:\n{plan_text}\n\n"
        f"Request: {user_request}\n\n"
        f"Evidence (JSON):\n{ev.compact(items)}"
    )
    if items:
        shown = items[:5]
        fallback = (
            f"RESULT: Based on {len(items)} evidence item(s): "
            + "; ".join(ev.describe(item) for item in shown)
            + "\nSOURCES: "
            + ", ".join(ev.label(item) for item in shown)
        )
    else:
        fallback = "RESULT: Insufficient evidence to complete the request.\nSOURCES: none"
    return run_agent("worker", user_prompt, fallback)