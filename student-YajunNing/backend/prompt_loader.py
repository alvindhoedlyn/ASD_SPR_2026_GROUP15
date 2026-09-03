"""Load version-controlled prompt assets for Flight AI mode."""

from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Missing prompt asset: {filename}")
    return prompt_path.read_text(encoding="utf-8").strip()
