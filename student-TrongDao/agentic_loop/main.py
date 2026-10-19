import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
AGENTIC_LOOP_DIR = THIS_FILE.parent
APP_DIR = AGENTIC_LOOP_DIR.parent
REPO_ROOT = APP_DIR.parent
LOG_DIRECTORY = APP_DIR / "reports" / "agentic-loop"

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

mcp_collector = load_local_module(
    "trongdao_mcp_collector",
    AGENTIC_LOOP_DIR
    / "collectors"
    / "mcp_collector.py"
)

rag_collector = load_local_module(
    "trongdao_rag_collector",
    AGENTIC_LOOP_DIR
    / "collectors"
    / "rag_collector.py"
)

testing_collector = load_local_module(
    "trongdao_testing_collector",
    AGENTIC_LOOP_DIR
    / "collectors"
    / "testing_collector.py"
)

multi_agent_collector = load_local_module(
    "trongdao_multi_agent_collector",
    AGENTIC_LOOP_DIR
    / "collectors"
    / "multi_agent_collector.py"
)

review_pipeline = load_local_module(
    "trongdao_review_pipeline",
    AGENTIC_LOOP_DIR
    / "pipelines"
    / "review_pipeline.py"
)

mcp_validation_pipeline = load_local_module(
    "trongdao_mcp_validation_pipeline",
    AGENTIC_LOOP_DIR
    / "pipelines"
    / "mcp_validation_pipeline.py"
)

rag_validation_pipeline = load_local_module(
    "trongdao_rag_validation_pipeline",
    AGENTIC_LOOP_DIR
    / "pipelines"
    / "rag_validation_pipeline.py"
)

testing_pipeline = load_local_module(
    "trongdao_testing_pipeline",
    AGENTIC_LOOP_DIR
    / "pipelines"
    / "testing_pipeline.py"
)

multi_agent_pipeline = load_local_module(
    "trongdao_multi_agent_pipeline",
    AGENTIC_LOOP_DIR
    / "pipelines"
    / "multi_agent_pipeline.py"
)


COLLECTORS = {
    "db": database_collector.collect,
    "endpoints": endpoints_collector.collect,
    "devops": devops_collector.collect,
    "mcp": mcp_collector.collect,
    "rag": rag_collector.collect,
    "testing": testing_collector.collect,
    "multi_agent": multi_agent_collector.collect
}


PIPELINES = {
    "db": review_pipeline,
    "endpoints": review_pipeline,
    "devops": review_pipeline,
    "mcp": mcp_validation_pipeline,
    "rag": rag_validation_pipeline,
    "testing": testing_pipeline,
    "multi_agent": multi_agent_pipeline
}


def run_review(
    mode_key,
    mode_config,
    prompts,
    ai_runner
):
    mode = mode_config[mode_key]
    collector = COLLECTORS[mode_key]
    pipeline = PIPELINES[mode_key]

    return run_mode(
        mode=mode,
        app_dir=APP_DIR,
        repo_root=REPO_ROOT,
        prompts=prompts,
        ai=ai_runner,
        collect_fn=collector,
        implementation_prompt_fn=(
            pipeline.build_implementation_prompt
        ),
        review_prompt_fn=(
            pipeline.build_review_prompt
        )
    )


def save_review_log(
    mode_key,
    mode_label,
    result
):
    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )

    log_path = (
        LOG_DIRECTORY
        / f"{mode_key}-validation-log.md"
    )

    log_path.write_text(
        (
            f"# {mode_label} - Validation Log\n\n"
            f"Run at: {timestamp}\n\n"
            f"{result}\n"
        ),
        encoding="utf-8"
    )

    return log_path


def run_and_report(
    mode_key,
    mode_config,
    prompts,
    ai_runner
):
    result = run_review(
        mode_key,
        mode_config,
        prompts,
        ai_runner
    )

    mode_label = mode_config[mode_key].label

    reporter.print_result(
        mode_label,
        result
    )

    log_path = save_review_log(
        mode_key,
        mode_label,
        result
    )

    print(
        "Validation log saved to "
        + str(log_path.relative_to(REPO_ROOT))
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
        ),
        "MCP": str(
            APP_DIR / "prompts" / "mcp"
        ),
        "RAG": str(
            APP_DIR / "prompts" / "rag"
        ),
        "Testing": str(
            APP_DIR / "prompts" / "testing"
        ),
        "Multi-Agent": str(
            APP_DIR / "prompts" / "multi_agent"
        )
    })

    while True:
        reporter.print_menu([
            ("1", "Database"),
            ("2", "Endpoints"),
            ("3", "DevOps"),
            ("4", "MCP"),
            ("5", "RAG"),
            ("6", "Run Release 1 Modes"),
            ("7", "Multi-Agent Workflow Review"),
            ("8", "Testing Report Review")
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
            "3": "devops",
            "4": "mcp",
            "5": "rag",
            "7": "multi_agent",
            "8": "testing"
        }

        if choice == "6":
            for mode_key in [
                "db",
                "endpoints",
                "devops",
                "mcp",
                "rag"
            ]:
                run_and_report(
                    mode_key,
                    mode_config,
                    prompts,
                    ai_runner
                )

            continue

        mode_key = choices.get(choice)

        if mode_key is None:
            print(
                "Invalid choice. "
                "Choose one of the displayed options."
            )
            continue

        run_and_report(
            mode_key,
            mode_config,
            prompts,
            ai_runner
        )


if __name__ == "__main__":
    main()
