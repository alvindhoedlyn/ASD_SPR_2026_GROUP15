"""
Interactive agentic loop entry point for the Accommodation Recommender.

Run from the repository root:
    python student-RenzoRobin/agentic_loop/main.py

Menu:
    1 - DB          (live database evidence)
    2 - Endpoints   (live HTTP evidence against the running backend)
    3 - DevOps      (CI/CD pipeline evidence)
    4 - MCP         (MCP tool-call validation)
    5 - RAG         (RAG grounded-answer validation)
    6 - Run modes 1-5
    7 - Multi-Agent Workflow Review   (Release 2)
    8 - Testing Report Review         (Release 2)
    9 - Cloud Deployment Report Review (Release 2)
    0 - Exit

Every run is also saved to student-RenzoRobin/reports/agentic-loop/
<mode>-validation-log.md so the review log can go into the report.
"""
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
APP_DIR = THIS_FILE.parent.parent          # student-RenzoRobin/
REPO_ROOT = APP_DIR.parent                 # repository root
LOG_DIR = APP_DIR / "reports" / "agentic-loop"

# The loop runs on the host, not in Docker, so point AIRunner at local Ollama.
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")

sys.path.insert(0, str(REPO_ROOT))
from shared.agentic_loop.core.ai_runner import AIRunner            # noqa: E402
from shared.agentic_loop.core.prompt_registry import PromptRegistry  # noqa: E402
from shared.agentic_loop.core.orchestrator import run_mode          # noqa: E402
from shared.agentic_loop.core import reporter                       # noqa: E402

from config.review_config import build_mode_config                  # noqa: E402

AGENTIC_LOOP_DIR = THIS_FILE.parent


def _load_local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collector(name: str):
    return _load_local_module(f"renzorobin_{name}_collector",
                              AGENTIC_LOOP_DIR / "collectors" / f"{name}_collector.py")


def _pipeline(name: str):
    return _load_local_module(f"renzorobin_{name}_pipeline",
                              AGENTIC_LOOP_DIR / "pipelines" / f"{name}_pipeline.py")


# mode key -> (collector module name, pipeline module name)
MODULES = {
    "db": ("db", "db"),
    "endpoints": ("endpoints", "endpoints"),
    "devops": ("devops", "architecture"),
    "mcp": ("mcp", "mcp_validation"),
    "rag": ("rag", "rag_validation"),
    "multi_agent": ("multi_agent", "multi_agent"),
    "testing": ("testing", "testing"),
    "cloud": ("cloud", "cloud"),
}
COLLECTORS = {key: _collector(c).collect for key, (c, _) in MODULES.items()}
PIPELINES = {key: _pipeline(p) for key, (_, p) in MODULES.items()}

MENU = {
    "1": "db", "2": "endpoints", "3": "devops", "4": "mcp", "5": "rag",
    "7": "multi_agent", "8": "testing", "9": "cloud",
}
RELEASE1_KEYS = ("db", "endpoints", "devops", "mcp", "rag")


def _run(mode_key: str, mode_config: dict, prompts: PromptRegistry, ai: AIRunner) -> str:
    mode = mode_config[mode_key]
    pipeline = PIPELINES[mode_key]
    return run_mode(mode, APP_DIR, REPO_ROOT, prompts, ai, COLLECTORS[mode_key],
                    implementation_prompt_fn=pipeline.build_implementation_prompt,
                    review_prompt_fn=pipeline.build_review_prompt)


def _save_log(mode_key: str, label: str, result: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{mode_key}-validation-log.md"
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    path.write_text(f"# {label} - validation log\n\nRun at: {stamp}\n\n{result}\n",
                    encoding="utf-8")
    return path


def _run_and_report(mode_key: str, mode_config: dict, prompts: PromptRegistry, ai: AIRunner) -> None:
    label = mode_config[mode_key].label
    result = _run(mode_key, mode_config, prompts, ai)
    reporter.print_result(label, result)
    print(f"Log saved to {_save_log(mode_key, label, result).relative_to(REPO_ROOT)}")


def main() -> None:
    mode_config = build_mode_config()
    prompts = PromptRegistry(APP_DIR)
    ai = AIRunner()

    print("AGENTIC LOOP - Accommodation Recommender (student-RenzoRobin)")
    reporter.print_prompt_map({
        "DB": str(APP_DIR / "prompts" / "service"),
        "Endpoints": str(APP_DIR / "prompts" / "service"),
        "DevOps": str(APP_DIR / "prompts" / "devops"),
        "MCP": str(APP_DIR / "prompts" / "mcp"),
        "RAG": str(APP_DIR / "prompts" / "rag"),
        "Multi-Agent": str(APP_DIR / "prompts" / "multi_agent"),
        "Testing": str(APP_DIR / "prompts" / "testing"),
        "Cloud": str(APP_DIR / "prompts" / "cloud"),
    })

    while True:
        reporter.print_menu([
            ("1", "DB"), ("2", "Endpoints"), ("3", "DevOps"),
            ("4", "MCP"), ("5", "RAG"), ("6", "Run modes 1-5"),
            ("7", "Multi-Agent Workflow"), ("8", "Testing Report"),
            ("9", "Cloud Deployment"),
        ])
        try:
            choice = input("Choose a review target (0 to exit): ").strip()
        except EOFError:
            choice = "0"

        if choice == "0":
            print("Loop closed.")
            break

        if choice == "6":
            for key in RELEASE1_KEYS:
                _run_and_report(key, mode_config, prompts, ai)
            continue

        mode_key = MENU.get(choice)
        if not mode_key:
            print("Invalid choice. Select 0-9.")
            continue

        _run_and_report(mode_key, mode_config, prompts, ai)


if __name__ == "__main__":
    main()