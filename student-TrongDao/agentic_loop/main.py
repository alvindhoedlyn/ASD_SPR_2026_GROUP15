import importlib.util
import os
import sys
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
AGENTIC_LOOP_DIR = THIS_FILE.parent
APP_DIR = AGENTIC_LOOP_DIR.parent
REPO_ROOT = APP_DIR.parent

sys.path.insert(0, str(REPO_ROOT))


from shared.agentic_loop.core.ai_runner import AIRunner
from shared.agentic_loop.core.orchestrator import run_mode
from shared.agentic_loop.core.prompt_registry import PromptRegistry
from shared.agentic_loop.core import reporter


def load_local_module(module_name, file_path):
    module_spec = importlib.util.spec_from_file_location(
        module_name,
        file_path
    )

    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    return module


config_module = load_local_module(
    "trongdao_review_config",
    AGENTIC_LOOP_DIR / "config" / "review_config.py"
)

database_collector = load_local_module(
    "trongdao_database_collector",
    AGENTIC_LOOP_DIR
    / "collectors"
    / "database_collector.py"
)

endpoints_collector = load_local_module(
    "trongdao_endpoints_collector",
    AGENTIC_LOOP_DIR
    / "collectors"
    / "endpoints_collector.py"
)

devops_collector = load_local_module(
    "trongdao_devops_collector",
    AGENTIC_LOOP_DIR
    / "collectors"
    / "devops_collector.py"
)

review_pipeline = load_local_module(
    "trongdao_review_pipeline",
    AGENTIC_LOOP_DIR
    / "pipelines"
    / "review_pipeline.py"
)


COLLECTORS = {
    "db": database_collector.collect,
    "endpoints": endpoints_collector.collect,
    "devops": devops_collector.collect
}


def run_review(
    mode_key,
    mode_config,
    prompts,
    ai_runner
):
    mode = mode_config[mode_key]
    collector = COLLECTORS[mode_key]

    return run_mode(
        mode=mode,
        app_dir=APP_DIR,
        repo_root=REPO_ROOT,
        prompts=prompts,
        ai=ai_runner,
        collect_fn=collector,
        implementation_prompt_fn=(
            review_pipeline.build_implementation_prompt
        ),
        review_prompt_fn=(
            review_pipeline.build_review_prompt
        )
    )


def main():
    os.environ.setdefault(
        "OLLAMA_BASE_URL",
        "http://localhost:11434/v1"
    )

    os.environ.setdefault(
        "OLLAMA_MODEL",
        "qwen2.5:0.5b"
    )

    os.environ.setdefault(
        "OLLAMA_REVIEW_MODEL",
        "llama3.1:8b"
    )

    mode_config = config_module.build_mode_config()
    prompts = PromptRegistry(APP_DIR)
    ai_runner = AIRunner()

    print()
    print(
        "AGENTIC LOOP - "
        "Location Recommender (Student 4)"
    )

    reporter.print_prompt_map({
        "Database": str(
            APP_DIR / "prompts" / "database"
        ),
        "Endpoints": str(
            APP_DIR / "prompts" / "endpoints"
        ),
        "DevOps": str(
            APP_DIR / "prompts" / "devops"
        )
    })

    while True:
        reporter.print_menu([
            ("1", "Database"),
            ("2", "Endpoints"),
            ("3", "DevOps"),
            ("4", "Run All")
        ])

        choice = input(
            "Choose a review target: "
        ).strip()

        if choice == "0":
            print("Agentic loop closed.")
            break

        choices = {
            "1": "db",
            "2": "endpoints",
            "3": "devops"
        }

        if choice == "4":
            for mode_key in [
                "db",
                "endpoints",
                "devops"
            ]:
                result = run_review(
                    mode_key,
                    mode_config,
                    prompts,
                    ai_runner
                )

                reporter.print_result(
                    mode_config[mode_key].label,
                    result
                )

            continue

        mode_key = choices.get(choice)

        if mode_key is None:
            print(
                "Invalid choice. "
                "Choose 0, 1, 2, 3, or 4."
            )
            continue

        result = run_review(
            mode_key,
            mode_config,
            prompts,
            ai_runner
        )

        reporter.print_result(
            mode_config[mode_key].label,
            result
        )


if __name__ == "__main__":
    main()