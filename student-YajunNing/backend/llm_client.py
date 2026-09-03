"""Ollama client using the same OpenAI-compatible interface as the Lab app."""

import json
import os
import re

from openai import OpenAI

from prompt_loader import load_prompt


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


def validate_grounded_explanation(explanation, search, recommendations):
    """Reject common invented facts before AI text reaches the frontend."""
    allowed_flight_numbers = {flight["flight_number"].upper() for flight in recommendations}
    mentioned_flight_numbers = set(re.findall(r"\b[A-Z]{1,3}\d{1,4}\b", explanation.upper()))
    if not mentioned_flight_numbers.issubset(allowed_flight_numbers):
        return False

    allowed_stops = {int(flight["stops"]) for flight in recommendations}
    mentioned_stops = {
        int(value) for value in re.findall(r"\b(\d+)\s+(?:stop|stops|stopover|stopovers)\b", explanation.lower())
    }
    if not mentioned_stops.issubset(allowed_stops):
        return False

    allowed_prices = {float(flight["price_aud"]) for flight in recommendations}
    allowed_prices.add(float(search["max_budget"]))
    mentioned_prices = {
        float(value) for value in re.findall(r"(?:AUD\s*\$?|\$)\s*(\d+(?:\.\d+)?)", explanation, re.IGNORECASE)
    }
    return mentioned_prices.issubset(allowed_prices)


def generate_ai_explanation(search, recommendations, agent_trace):
    system_prompt = load_prompt("flight_recommendation_system.txt")
    task_template = load_prompt("flight_recommendation_task.txt")
    task_prompt = (
        task_template
        .replace("{{SEARCH}}", json.dumps(search, ensure_ascii=False))
        .replace("{{FLIGHTS}}", json.dumps(recommendations, ensure_ascii=False))
        .replace("{{AGENT_TRACE}}", json.dumps(agent_trace, ensure_ascii=False))
    )

    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", timeout=45.0)
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt},
        ],
        max_tokens=140,
        temperature=0.1,
    )
    explanation = (response.choices[0].message.content or "").strip()
    if not explanation:
        raise ValueError("AI returned an empty explanation")
    if not validate_grounded_explanation(explanation, search, recommendations):
        raise ValueError("AI explanation failed grounding validation")
    return explanation
