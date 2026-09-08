from shared.agentic_loop.config.review_config import ModeConfig


def build_mode_config() -> dict[str, ModeConfig]:
    return {
                "db": ModeConfig(
            key="db",
            label="DB",
            prompt_family="service",
            implementation_prompts=(
                "implementation/system_prompt.txt",
                "implementation/task_prompt.txt",
                "implementation/context_prompt.txt",
            ),
            review_prompts=("review/review_prompt.txt",),
            two_stage=True,
        ),
        "endpoints": ModeConfig(
            key="endpoints",
            label="Endpoints",
            prompt_family="service",
            implementation_prompts=(
                "implementation/system_prompt.txt",
                "implementation/task_prompt.txt",
                "implementation/context_prompt.txt",
            ),
            review_prompts=("review/review_prompt.txt",),
            two_stage=True,
        ),
        "devops": ModeConfig(
            key="devops",
            label="DevOps",
            prompt_family="devops",
            implementation_prompts=(
                "implementation/system_prompt.txt",
                "implementation/task_prompt.txt",
            ),
            review_prompts=("review/review_prompt.txt",),
            two_stage=True,
        ),
    }