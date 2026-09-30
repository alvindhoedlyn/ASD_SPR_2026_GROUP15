"""Agentic Budget Advisor using Plan-Act-Observe-Adapt.

Release 1 integrates:
- Shared MCP for live Budget Tracker data
- Shared RAG for approved knowledge
- Validation of MCP and RAG observations
- Local Ollama/Qwen for grounded adaptation
"""

from llm_client import generate_response
from mcp_client import (
    get_budget_expenses_via_mcp,
    get_budget_summary_via_mcp,
)
from rag_client import query_rag


def run_budget_agent():
    """
    Run the Release 1 Budget Advisor agent.

    Flow:
        PLAN
        ACT      -> Shared MCP + Shared RAG
        OBSERVE  -> Validate MCP and RAG results
        ADAPT    -> Local Qwen generates grounded advice
    """

    trace = []

    # =====================================================
    # PLAN
    # =====================================================

    trace.append({
        "stage": "Plan",
        "detail": (
            "Collect live Budget Tracker data through the shared MCP "
            "server and retrieve approved Budget Tracker knowledge "
            "through the shared RAG server before generating advice."
        ),
    })

    # =====================================================
    # ACT
    # =====================================================

    budget_summary = get_budget_summary_via_mcp()
    expenses = get_budget_expenses_via_mcp()

    rag_result = query_rag(
        "How should remaining budget and current spending be "
        "interpreted in the Budget Tracker?"
    )

    trace.append({
        "stage": "Act",
        "detail": (
            "Called the shared MCP budget_summary and budget_expenses "
            "tools and queried the shared RAG knowledge service."
        ),
    })

    # =====================================================
    # OBSERVE - MCP VALIDATION
    # =====================================================

    if not isinstance(budget_summary, dict):
        raise RuntimeError(
            "MCP validation failed: budget_summary did not return "
            "a dictionary."
        )

    if not isinstance(expenses, list):
        raise RuntimeError(
            "MCP validation failed: budget_expenses did not return "
            "a list."
        )

    required_summary_fields = {
        "total_budget",
        "total_spent",
        "remaining_budget",
    }

    missing_fields = required_summary_fields.difference(
        budget_summary.keys()
    )

    if missing_fields:
        raise RuntimeError(
            "MCP validation failed: missing budget summary field(s): "
            + ", ".join(sorted(missing_fields))
        )

    total_budget = float(
        budget_summary.get("total_budget", 0) or 0
    )

    total_spent = float(
        budget_summary.get("total_spent", 0) or 0
    )

    remaining_budget = float(
        budget_summary.get(
            "remaining_budget",
            total_budget - total_spent,
        ) or 0
    )

    min_price = float(
        budget_summary.get("min_price", 0) or 0
    )

    max_price = float(
        budget_summary.get("max_price", 0) or 0
    )

    calculated_remaining = total_budget - total_spent

    if abs(remaining_budget - calculated_remaining) > 0.01:
        raise RuntimeError(
            "MCP validation failed: remaining budget does not match "
            "total budget minus total spent."
        )

    trace.append({
        "stage": "Observe - MCP Validation",
        "detail": (
            f"MCP data validated successfully. Total budget is "
            f"AUD ${total_budget:.2f}, total spent is "
            f"AUD ${total_spent:.2f}, remaining budget is "
            f"AUD ${remaining_budget:.2f}, and "
            f"{len(expenses)} expense record(s) were returned."
        ),
    })

    # =====================================================
    # OBSERVE - EXPENSE VALIDATION
    # =====================================================

    category_totals = {}

    for expense in expenses:
        if not isinstance(expense, dict):
            raise RuntimeError(
                "MCP validation failed: an expense record is invalid."
            )

        category = str(
            expense.get("category", "Other")
        )

        amount = float(
            expense.get("amount", 0) or 0
        )

        category_totals[category] = (
            category_totals.get(category, 0)
            + amount
        )

    if category_totals:
        highest_category = max(
            category_totals,
            key=category_totals.get,
        )

        highest_category_amount = (
            category_totals[highest_category]
        )
    else:
        highest_category = "None"
        highest_category_amount = 0

    if total_budget > 0:
        spending_percentage = (
            total_spent / total_budget
        ) * 100
    else:
        spending_percentage = 0

    # =====================================================
    # OBSERVE - RAG VALIDATION
    # =====================================================

    if not isinstance(rag_result, dict):
        raise RuntimeError(
            "RAG validation failed: response is not a dictionary."
        )

    rag_answer = str(
        rag_result.get("answer", "")
    ).strip()

    rag_confidence = str(
        rag_result.get("confidence", "insufficient")
    ).strip().lower()

    rag_sources = rag_result.get("sources", [])

    if not rag_answer:
        raise RuntimeError(
            "RAG validation failed: no grounded answer was returned."
        )

    if rag_confidence == "insufficient":
        raise RuntimeError(
            "RAG validation failed: knowledge context was insufficient."
        )

    if not isinstance(rag_sources, list) or not rag_sources:
        raise RuntimeError(
            "RAG validation failed: no source citation was returned."
        )

    first_source = rag_sources[0]

    if isinstance(first_source, dict):
        rag_document = str(
            first_source.get("document", "Unknown source")
        )

        rag_section = str(
            first_source.get("section", "Unknown section")
        )
    else:
        rag_document = str(first_source)
        rag_section = "Unknown section"

    trace.append({
        "stage": "Observe - RAG Validation",
        "detail": (
            f"RAG response validated with confidence "
            f"'{rag_confidence}'. Grounding source: "
            f"{rag_document}, section: {rag_section}."
        ),
    })

    # =====================================================
    # ADAPT
    # =====================================================

    prompt = f"""
You are a travel budget advisor.

Use ONLY the validated MCP budget data and the approved RAG
knowledge supplied below.

Do not invent expenses, prices, financial information, or sources.

VALIDATED MCP BUDGET DATA

Total budget: AUD ${total_budget:.2f}
Total spent: AUD ${total_spent:.2f}
Remaining budget: AUD ${remaining_budget:.2f}
Budget used: {spending_percentage:.1f}%

Preferred minimum price: AUD ${min_price:.2f}
Preferred maximum price: AUD ${max_price:.2f}

Spending by category:
{category_totals}

Highest spending category:
{highest_category} - AUD ${highest_category_amount:.2f}

APPROVED RAG KNOWLEDGE

{rag_answer}

RAG confidence:
{rag_confidence}

RAG source:
{rag_document} - {rag_section}

Give the traveller:
1. A short assessment of the current budget.
2. One practical recommendation.
3. A warning if spending is becoming risky.

Keep the answer concise and grounded in the supplied information.
"""

    advice = generate_response(prompt)

    if not advice:
        raise RuntimeError(
            "Agent adaptation failed: local Qwen returned no advice."
        )

    trace.append({
        "stage": "Adapt",
        "detail": (
            "Generated grounded budget advice using local Qwen after "
            "successful MCP and RAG validation."
        ),
    })

    # =====================================================
    # RESULT
    # =====================================================

    return {
        "summary": {
            "total_budget": round(
                total_budget,
                2,
            ),
            "total_spent": round(
                total_spent,
                2,
            ),
            "remaining_budget": round(
                remaining_budget,
                2,
            ),
            "spending_percentage": round(
                spending_percentage,
                1,
            ),
            "highest_category": highest_category,
            "highest_category_amount": round(
                highest_category_amount,
                2,
            ),
            "min_price": round(
                min_price,
                2,
            ),
            "max_price": round(
                max_price,
                2,
            ),
        },
        "advice": advice,
        "validation": {
            "mcp": {
                "status": "passed",
                "expense_records": len(expenses),
            },
            "rag": {
                "status": "passed",
                "confidence": rag_confidence,
                "source": rag_document,
                "section": rag_section,
            },
            "local_ai": {
                "status": "passed",
                "model": "qwen2.5:0.5b",
            },
        },
        "trace": trace,
    }