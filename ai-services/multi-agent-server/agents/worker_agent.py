"""Worker agent: carries out the plan using only the supplied evidence."""
import evidence as ev
from agents.base import run_agent


def _fallback(user_request, items):
    """Deterministic answer. If the request asks for a listed term (e.g. breakfast),
    only the records that list it are returned, so the fallback is still correct."""
    if not items:
        return "RESULT: Insufficient evidence to complete the request.\nSOURCES: none"
    terms = ev.requested_terms(user_request, items)
    chosen = [i for i in items if all(t in ev.list_terms(i) for t in terms)] if terms else items
    wanted = " and ".join(f"'{t}'" for t in terms)
    if terms and not chosen:
        return f"RESULT: No evidence item lists {wanted}.\nSOURCES: none"
    shown = chosen[:ev.MAX_ITEMS]
    scope = f"{len(chosen)} of {len(items)} item(s) list {wanted}" if terms else f"{len(items)} evidence item(s)"
    return (
        f"RESULT: {scope}: " + "; ".join(ev.describe(item) for item in shown)
        + "\nSOURCES: " + ", ".join(ev.label(item) for item in shown)
    )


def run(user_request, plan_text, items):
    user_prompt = (
        f"Plan:\n{plan_text}\n\n"
        f"Request: {user_request}\n\n"
        f"Evidence ({len(items)} item(s)):\n{ev.brief(items)}\n\n"
        "Now write only the RESULT and SOURCES lines. Do not repeat the plan, request or evidence."
    )
    return run_agent("worker", user_prompt, _fallback(user_request, items), required=("RESULT:",))