from shared.agentic_loop.config.review_config import ModeConfig


def mode(key, label, family):
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


def build_mode_config():
    return {
        "multi_agent": mode("multi_agent", "Multi-Agent Workflow Review", "multi_agent"),
        "testing": mode("testing", "Testing Report Review", "testing"),
        "cloud": mode("cloud", "Cloud Deployment Report Review", "cloud"),
    }
