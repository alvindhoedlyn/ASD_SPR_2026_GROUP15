"""SHARED console output helpers — no app-specific knowledge."""


def print_prompt_map(mapping: dict[str, str]) -> None:
    print("PROMPT PATH MAP")
    for label, path in mapping.items():
        print(f"- {label}: {path}")


def print_menu(options: list[tuple[str, str]]) -> None:
    """options: list of (key, label) pairs, e.g. [("1", "DB"), ("2", "Endpoints")]"""
    print()
    print("=" * 70)
    print("AGENTIC REVIEW MENU")
    for key, label in options:
        print(f"{key} - {label}")
    print("0 - Exit")
    print("=" * 70)


def print_result(title: str, text: str) -> None:
    print()
    print(f"RUNNING: {title}")
    print(text)


def stage(mode_label: str, step: str, message: str) -> None:
    print(f"[{mode_label}][{step}] {message}")