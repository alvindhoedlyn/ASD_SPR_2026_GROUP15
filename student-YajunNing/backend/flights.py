"""Deterministic ranking logic for flight records supplied by database-service."""


def _normalise(value, minimum, maximum):
    if minimum == maximum:
        return 0
    return (value - minimum) / (maximum - minimum)


def _best_overall_score(flight, candidates):
    prices = [item["price_aud"] for item in candidates]
    durations = [item["duration_minutes"] for item in candidates]
    stops = [item["stops"] for item in candidates]

    weighted_cost = (
        0.5 * _normalise(flight["price_aud"], min(prices), max(prices))
        + 0.3 * _normalise(flight["duration_minutes"], min(durations), max(durations))
        + 0.2 * _normalise(flight["stops"], min(stops), max(stops))
    )
    return round(100 * (1 - weighted_cost), 1)


def _reason_for(flight, preference):
    if preference == "cheapest":
        return f"Strong price match at AUD ${flight['price_aud']}."
    if preference == "fastest":
        return f"Prioritised for its {flight['duration_minutes'] // 60}h {flight['duration_minutes'] % 60}m travel time."
    if preference == "fewest_stops":
        return "Direct flight with no stopovers." if flight["stops"] == 0 else "Best available option with one stop."
    return "Balanced using price, travel time, and number of stops."


def rank_flights(available_flights, preference):
    """Return up to three supplied flights in the requested order."""
    candidates = [flight.copy() for flight in available_flights]
    if not candidates:
        return []

    for flight in candidates:
        flight["score"] = _best_overall_score(flight, candidates)
        flight["reason"] = _reason_for(flight, preference)

    sort_keys = {
        "best_overall": lambda item: (-item["score"], item["price_aud"]),
        "cheapest": lambda item: (item["price_aud"], item["duration_minutes"]),
        "fastest": lambda item: (item["duration_minutes"], item["price_aud"]),
        "fewest_stops": lambda item: (item["stops"], item["duration_minutes"], item["price_aud"]),
    }
    candidates.sort(key=sort_keys[preference])
    return candidates[:3]


def build_grounded_fallback(search, recommendations):
    """Create a safe explanation using application-owned facts only."""
    leading = recommendations[0]
    stop_description = "is direct" if leading["stops"] == 0 else f"has {leading['stops']} stop"
    preference = search["preference"].replace("_", " ")
    return (
        f"{leading['flight_number']} is the top {preference} match from the supplied catalogue. "
        f"It costs AUD ${leading['price_aud']:.0f}, takes "
        f"{leading['duration_minutes'] // 60}h {leading['duration_minutes'] % 60}m, and {stop_description}."
    )
