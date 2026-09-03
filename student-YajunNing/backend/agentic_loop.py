"""Bounded Plan-Act-Observe-Adapt loop for grounded flight recommendations."""

from database_client import get_available_flights
from flights import rank_flights


def _route_flights(flights):
    return [
        flight for flight in flights
        if flight["origin"] == "SYD" and flight["destination"] in {"NRT", "HND"}
    ]


def run_flight_agent(search):
    """Return recommendations and an auditable four-stage execution trace."""
    budget = float(search["max_budget"])
    preference = search["preference"]
    trace = [{
        "stage": "Plan",
        "detail": (
            f"Find Sydney-to-Tokyo flights within AUD ${budget:.0f} and prioritise "
            f"{preference.replace('_', ' ')}."
        ),
    }]

    matching_flights = _route_flights(get_available_flights(budget))
    recommendations = rank_flights(matching_flights, preference)
    trace.append({
        "stage": "Act",
        "detail": f"Retrieved {len(matching_flights)} matching catalogue flights and ranked them deterministically.",
    })
    trace.append({
        "stage": "Observe",
        "detail": (
            f"Found {len(recommendations)} recommendation(s) within budget."
            if recommendations
            else "No catalogue flight satisfies the current budget."
        ),
    })

    if recommendations:
        trace.append({
            "stage": "Adapt",
            "detail": "No constraint relaxation was required; preserve the traveller's budget.",
        })
        return {
            "recommendations": recommendations,
            "available_count": len(matching_flights),
            "adapted": False,
            "message": None,
            "trace": trace,
        }

    all_route_flights = _route_flights(get_available_flights())
    if not all_route_flights:
        trace.append({
            "stage": "Adapt",
            "detail": "No route alternative exists in the supplied catalogue; do not invent one.",
        })
        return {
            "recommendations": [],
            "available_count": 0,
            "adapted": False,
            "message": "No catalogue flights are available for this route.",
            "trace": trace,
        }

    nearest_price = min(flight["price_aud"] for flight in all_route_flights)
    nearest_options = [
        flight for flight in all_route_flights if flight["price_aud"] == nearest_price
    ]
    recommendations = rank_flights(nearest_options, preference)
    increase = nearest_price - budget
    message = (
        f"No flight fits AUD ${budget:.0f}. The nearest catalogue option requires "
        f"AUD ${increase:.0f} more."
    )
    trace.append({
        "stage": "Adapt",
        "detail": (
            f"Show only the nearest real catalogue option at AUD ${nearest_price:.0f}; "
            "label the budget increase explicitly."
        ),
    })
    return {
        "recommendations": recommendations,
        "available_count": 0,
        "adapted": True,
        "message": message,
        "trace": trace,
    }
