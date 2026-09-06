"""Agentic Budget Advisor using Plan-Act-Observe-Adapt."""

from database_client import get_budget, get_expenses
from llm_client import generate_response


def run_budget_agent():
    """
    Run a bounded Plan-Act-Observe-Adapt loop.

    The agent:
    1. Plans what budget information is needed.
    2. Acts by retrieving real data from the database service.
    3. Observes deterministic budget calculations.
    4. Adapts by asking the LLM for grounded budget advice.
    """

    trace = []

    # =====================================================
    # PLAN
    # =====================================================

    trace.append({
        "stage": "Plan",
        "detail": (
            "Analyse the traveller's current budget, expenses, "
            "remaining money and spending categories before "
            "providing budget advice."
        )
    })

    # =====================================================
    # ACT
    # =====================================================

    budget = get_budget()
    expenses = get_expenses()

    trace.append({
        "stage": "Act",
        "detail": (
            f"Retrieved the current budget settings and "
            f"{len(expenses)} expense record(s) from the "
            "database microservice."
        )
    })

    # =====================================================
    # OBSERVE
    # =====================================================

    total_budget = float(
        budget.get("total_budget", 0) or 0
    )

    min_price = float(
        budget.get("min_price", 0) or 0
    )

    max_price = float(
        budget.get("max_price", 0) or 0
    )

    total_spent = sum(
        float(expense.get("amount", 0) or 0)
        for expense in expenses
    )

    remaining_budget = total_budget - total_spent

    category_totals = {}

    for expense in expenses:
        category = expense.get(
            "category",
            "Other"
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
            key=category_totals.get
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

    trace.append({
        "stage": "Observe",
        "detail": (
            f"Total budget is AUD ${total_budget:.2f}, "
            f"total spent is AUD ${total_spent:.2f}, "
            f"and remaining budget is "
            f"AUD ${remaining_budget:.2f}. "
            f"The highest spending category is "
            f"{highest_category} at "
            f"AUD ${highest_category_amount:.2f}."
        )
    })

    # =====================================================
    # ADAPT
    # =====================================================

    prompt = f"""
You are a travel budget advisor.

Use ONLY the following real budget data.
Do not invent expenses, prices or financial information.

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

Give the traveller:
1. A short assessment of the current budget.
2. One practical recommendation.
3. A warning if spending is becoming risky.

Keep the answer concise.
"""

    advice = generate_response(prompt)

    trace.append({
        "stage": "Adapt",
        "detail": (
            "Generated grounded budget advice using "
            "Qwen based on the observed budget data."
        )
    })

    # =====================================================
    # RESULT
    # =====================================================

    return {
        "summary": {
            "total_budget": round(
                total_budget,
                2
            ),
            "total_spent": round(
                total_spent,
                2
            ),
            "remaining_budget": round(
                remaining_budget,
                2
            ),
            "spending_percentage": round(
                spending_percentage,
                1
            ),
            "highest_category": (
                highest_category
            ),
            "highest_category_amount": round(
                highest_category_amount,
                2
            ),
            "min_price": round(
                min_price,
                2
            ),
            "max_price": round(
                max_price,
                2
            )
        },
        "advice": advice,
        "trace": trace
    }