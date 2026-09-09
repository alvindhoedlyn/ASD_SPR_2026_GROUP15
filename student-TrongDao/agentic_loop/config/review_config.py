from shared.agentic_loop.config.review_config import ModeConfig


def build_mode_config():
    return {
        "db": ModeConfig(
            key="db",
            label="Database Review",
            prompt_family="database",
            implementation_prompts=(
                "implementation/system_prompt.txt",
                "implementation/task_prompt.txt"
            ),
            review_prompts=(
                "review/review_prompt.txt",
            ),
            two_stage=True
        ),

        "endpoints": ModeConfig(
            key="endpoints",
            label="Endpoint Review",
            prompt_family="endpoints",
            implementation_prompts=(
                "implementation/system_prompt.txt",
                "implementation/task_prompt.txt"
            ),
            review_prompts=(
                "review/review_prompt.txt",
            ),
            two_stage=True
        ),

        "devops": ModeConfig(
            key="devops",
            label="DevOps Review",
            prompt_family="devops",
            implementation_prompts=(
                "implementation/system_prompt.txt",
                "implementation/task_prompt.txt"
            ),
            review_prompts=(
                "review/review_prompt.txt",
            ),
            two_stage=True
        )
    }