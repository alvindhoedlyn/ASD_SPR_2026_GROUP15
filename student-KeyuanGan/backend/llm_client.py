import os

import requests


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://ai-mode:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:0.5b"
)


def generate_response(prompt):
    """
    Send a prompt to Ollama and return the generated response.
    """

    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        return data.get("response", "").strip()

    except requests.RequestException as error:
        raise RuntimeError(
            f"Unable to communicate with Ollama: {error}"
        ) from error