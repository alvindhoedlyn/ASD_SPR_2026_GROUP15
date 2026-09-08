"""
Interactive agentic loop entry point for the Accommodation Recommender.

Run from the repository root:
    python student-RenzoRobin/agentic_loop/main.py

Menu:
    1 - DB          (live database evidence)
    2 - Endpoints   (live HTTP evidence against the running backend)
    3 - DevOps      (CI/CD pipeline evidence, two-stage implementation+review)
    4 - Run All
    0 - Exit
"""
import importlib.util
import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
APP_DIR = THIS_FILE.parent.parent          # student-RenzoRobin/
REPO_ROOT = APP_DIR.parent                 # repository root

sys.path.insert(0, str(REPO_ROOT))
from shared.agentic_loop.core.ai_runner import AIRunner            # noqa: E402
from shared.agentic_loop.core.prompt_registry import PromptRegistry  # noqa: E402
from shared.agentic_loop.core.orchestrator import run_mode          # noqa: E402
from shared.agentic_loop.core import reporter                       # noqa: E402

from config.review_config import build_mode_config                  # noqa: E402


def _load_local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGENTIC_LOOP_DIR = THIS_FILE.parent
db_collector = _load_local_module("renzorobin_db_collector", AGENTIC_LOOP_DIR / "collectors" / "db_collector.py")
endpoints_collector = _load_local_module("renzorobin_endpoints_collector", AGENTIC_LOOP_DIR / "collectors" / "endpoints_collector.py")
devops_collector = _load_local_module("renzorobin_devops_collector", AGENTIC_LOOP_DIR / "collectors" / "devops_collector.py")
db_pipeline = _load_local_module("renzorobin_db_pipeline", AGENTIC_LOOP_DIR / "pipelines" / "db_pipeline.py")
endpoints_pipeline = _load_local_module("renzorobin_endpoints_pipeline", AGENTIC_LOOP_DIR / "pipelines" / "endpoints_pipeline.py")
architecture_pipeline = _load_local_module("renzorobin_architecture_pipeline", AGENTIC_LOOP_DIR / "pipelines" / "architecture_pipeline.py")

COLLECTORS = {
    "db": db_collector.collect,
    "endpoints": endpoints_collector.collect,
    "devops": devops_collector.collect,
}


def _menu_choice_to_key(choice: str) -> str | None:
    return {"1": "db", "2": "endpoints", "3": "devops"}.get(choice)


def _run(mode_key: str, mode_config: dict, prompts: PromptRegistry, ai: AIRunner) -> str:
    mode = mode_config[mode_key]
    collect_fn = COLLECTORS[mode_key]

    if mode_key == "db":
        return run_mode(mode, APP_DIR, REPO_ROOT, prompts, ai, collect_fn,
                         implementation_prompt_fn=db_pipeline.build_implementation_prompt,
                         review_prompt_fn=db_pipeline.build_review_prompt)
    if mode_key == "endpoints":
        return run_mode(mode, APP_DIR, REPO_ROOT, prompts, ai, collect_fn,
                         implementation_prompt_fn=endpoints_pipeline.build_implementation_prompt,
                         review_prompt_fn=endpoints_pipeline.build_review_prompt)
    if mode_key == "devops":
        return run_mode(mode, APP_DIR, REPO_ROOT, prompts, ai, collect_fn,
                         implementation_prompt_fn=architecture_pipeline.build_implementation_prompt,
                         review_prompt_fn=architecture_pipeline.build_review_prompt)
    raise ValueError(f"Unknown mode: {mode_key}")


def main() -> None:
    mode_config = build_mode_config()
    prompts = PromptRegistry(APP_DIR)
    ai = AIRunner()

    print("AGENTIC LOOP — Accommodation Recommender (student-RenzoRobin)")
    reporter.print_prompt_map({
        "DB": str(APP_DIR / "prompts" / "service"),
        "Endpoints": str(APP_DIR / "prompts" / "service"),
        "DevOps": str(APP_DIR / "prompts" / "devops"),
    })

    while True:
        reporter.print_menu([("1", "DB"), ("2", "Endpoints"), ("3", "DevOps"), ("4", "Run All")])
        choice = input("Choose a review target: ").strip()

        if choice == "0":
            print("Loop closed.")
            break

        if choice == "4":
            for key in ("db", "endpoints", "devops"):
                result = _run(key, mode_config, prompts, ai)
                reporter.print_result(mode_config[key].label, result)
            continue

        mode_key = _menu_choice_to_key(choice)
        if not mode_key:
            print("Invalid choice. Select 0, 1, 2, 3, or 4.")
            continue

        result = _run(mode_key, mode_config, prompts, ai)
        reporter.print_result(mode_config[mode_key].label, result)


if __name__ == "__main__":
    main()