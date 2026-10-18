from shared.agentic_loop.config.review_config import ModeConfig


def _two_stage(key: str, label: str, family: str) -> ModeConfig:
    return ModeConfig(
        key=key,
        label=label,
        prompt_family=family,
        implementation_prompts=(
            "implementation/system_prompt.txt",
            "implementation/task_prompt.txt",
        ),
        review_prompts=("review/review_prompt.txt",),
        two_stage=True,
    )


def build_mode_config() -> dict[str, ModeConfig]:
    service_prompts = (
        "implementation/system_prompt.txt",
        "implementation/task_prompt.txt",
        "implementation/context_prompt.txt",
    )
    return {
        "db": ModeConfig(
            key="db", label="DB", prompt_family="service",
            implementation_prompts=service_prompts,
            review_prompts=("review/review_prompt.txt",), two_stage=True,
        ),
        "endpoints": ModeConfig(
            key="endpoints", label="Endpoints", prompt_family="service",
            implementation_prompts=service_prompts,
            review_prompts=("review/review_prompt.txt",), two_stage=True,
        ),
        "devops": _two_stage("devops", "DevOps", "devops"),
        "mcp": _two_stage("mcp", "MCP", "mcp"),
        "rag": _two_stage("rag", "RAG", "rag"),
        # ---- Release 2 modes ----
        "multi_agent": _two_stage("multi_agent", "Multi-Agent Workflow Review", "multi_agent"),
        "testing": _two_stage("testing", "Testing Report Review", "testing"),
        "cloud": _two_stage("cloud", "Cloud Deployment Report Review", "cloud"),
    }