"""Student 5 Release 2 agentic-loop review modes.

Run from the repository root:
    python student-YajunNing/agentic_loop/main.py
    python student-YajunNing/agentic_loop/main.py --mode multi-agent
    python student-YajunNing/agentic_loop/main.py --mode testing
    python student-YajunNing/agentic_loop/main.py --mode cloud
"""

import argparse
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path


AGENTIC_LOOP_DIRECTORY = Path(__file__).resolve().parent
APP_DIRECTORY = AGENTIC_LOOP_DIRECTORY.parent
REPOSITORY_ROOT = APP_DIRECTORY.parent
LOG_DIRECTORY = APP_DIRECTORY / "reports" / "agentic-loop"
sys.path.insert(0, str(REPOSITORY_ROOT))

from shared.agentic_loop.core import reporter  # noqa: E402
from shared.agentic_loop.core.ai_runner import AIRunner  # noqa: E402
from shared.agentic_loop.core.orchestrator import run_mode  # noqa: E402
from shared.agentic_loop.core.prompt_registry import PromptRegistry  # noqa: E402


def load_local_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config_module = load_local_module(
    "yajun_release2_review_config",
    AGENTIC_LOOP_DIRECTORY / "config" / "review_config.py",
)
pipeline = load_local_module(
    "yajun_release2_review_pipeline",
    AGENTIC_LOOP_DIRECTORY / "pipelines" / "review_pipeline.py",
)

COLLECTORS = {
    key: load_local_module(
        f"yajun_{key}_collector",
        AGENTIC_LOOP_DIRECTORY / "collectors" / f"{key}_collector.py",
    ).collect
    for key in ("multi_agent", "testing", "cloud")
}


def run_review(mode_key, mode_config, prompts, ai_runner):
    mode = mode_config[mode_key]
    return run_mode(
        mode=mode,
        app_dir=APP_DIRECTORY,
        repo_root=REPOSITORY_ROOT,
        prompts=prompts,
        ai=ai_runner,
        collect_fn=COLLECTORS[mode_key],
        implementation_prompt_fn=pipeline.build_implementation_prompt,
        review_prompt_fn=pipeline.build_review_prompt,
    )


def save_log(mode_key, label, result):
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    path = LOG_DIRECTORY / f"{mode_key}-validation-log.md"
    path.write_text(
        f"# {label} - Validation Log\n\nRun at: {timestamp}\n\n{result}\n",
        encoding="utf-8",
    )
    return path


def run_and_report(mode_key, mode_config, prompts, ai_runner):
    result = run_review(mode_key, mode_config, prompts, ai_runner)
    label = mode_config[mode_key].label
    reporter.print_result(label, result)
    log_path = save_log(mode_key, label, result)
    print(f"Validation log saved to {log_path.relative_to(REPOSITORY_ROOT)}")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Student 5 Release 2 review modes")
    parser.add_argument(
        "--mode",
        choices=("multi-agent", "testing", "cloud", "all"),
        help="Run one review non-interactively; omit for the menu.",
    )
    return parser.parse_args()


def main():
    os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:0.5b")
    os.environ.setdefault("OLLAMA_REVIEW_MODEL", "llama3.1:8b")

    arguments = parse_arguments()
    mode_config = config_module.build_mode_config()
    prompts = PromptRegistry(APP_DIRECTORY)
    ai_runner = AIRunner()
    aliases = {"multi-agent": "multi_agent", "testing": "testing", "cloud": "cloud"}

    if arguments.mode:
        selected = tuple(aliases.values()) if arguments.mode == "all" else (aliases[arguments.mode],)
        for mode_key in selected:
            run_and_report(mode_key, mode_config, prompts, ai_runner)
        return

    reporter.print_prompt_map({
        "Multi-Agent": str(APP_DIRECTORY / "prompts" / "multi_agent"),
        "Testing": str(APP_DIRECTORY / "prompts" / "testing"),
        "Cloud": str(APP_DIRECTORY / "prompts" / "cloud"),
    })
    choices = {"7": "multi_agent", "8": "testing", "9": "cloud"}
    while True:
        reporter.print_menu([
            ("7", "Multi-Agent Workflow Review"),
            ("8", "Testing Report Review"),
            ("9", "Cloud Deployment Report Review"),
        ])
        try:
            choice = input("Choose a review target: ").strip()
        except EOFError:
            choice = "0"
        if choice == "0":
            break
        mode_key = choices.get(choice)
        if mode_key:
            run_and_report(mode_key, mode_config, prompts, ai_runner)
        else:
            print("Invalid choice. Select 0, 7, 8 or 9.")


if __name__ == "__main__":
    main()
