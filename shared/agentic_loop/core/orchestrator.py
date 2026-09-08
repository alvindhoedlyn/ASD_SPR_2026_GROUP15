"""
SHARED orchestrator. Runs: START -> OBSERVE -> PROMPTS -> LLM -> [REVIEW] -> DONE

Unlike the reference lab's orchestrator.py (which imports its app's specific
collectors/pipelines directly), this version takes the collector and prompt
builder functions as parameters. That keeps this file genuinely shareable
across every student's agentic_loop, rather than each student needing their
own copy of the orchestration logic.

Two shapes of mode are supported (set via ModeConfig.two_stage):
  - single-stage (DB, Endpoints style): one implementation LLM call
  - two-stage (Architecture/DevOps style): implementation call, then an
    independent review call that critiques the first output
"""
from pathlib import Path
from typing import Callable

from shared.agentic_loop.config.review_config import ModeConfig
from shared.agentic_loop.core.ai_runner import AIRunner
from shared.agentic_loop.core.prompt_registry import PromptRegistry
from shared.agentic_loop.core import reporter

CollectFn = Callable[[Path, Path], tuple[bool, str]]
SingleStagePromptFn = Callable[[str, str, str], str]
ImplementationPromptFn = Callable[[str, str], str]
ReviewPromptFn = Callable[[str, str], str]


def run_mode(
    mode: ModeConfig,
    app_dir: Path,
    repo_root: Path,
    prompts: PromptRegistry,
    ai: AIRunner,
    collect_fn: CollectFn,
    single_stage_prompt_fn: SingleStagePromptFn | None = None,
    implementation_prompt_fn: ImplementationPromptFn | None = None,
    review_prompt_fn: ReviewPromptFn | None = None,
) -> str:
    reporter.stage(mode.label, "START", "Starting review flow")

    # ---- OBSERVE ----
    reporter.stage(mode.label, "OBSERVE", "Collecting evidence")
    ok, evidence = collect_fn(app_dir, repo_root)
    if not ok:
        reporter.stage(mode.label, "OBSERVE", "Failed")
        return f"OBSERVE FAILED: {evidence}"
    reporter.stage(mode.label, "OBSERVE", "Complete")

    # ---- SINGLE-STAGE (DB / Endpoints style) ----
    if not mode.two_stage:
        reporter.stage(mode.label, "PROMPTS", f"Loading prompt family: {mode.prompt_family}")
        system_prompt = prompts.read(mode.prompt_family, mode.implementation_prompts[0])
        task_prompt = prompts.read(mode.prompt_family, mode.implementation_prompts[1])
        context_prompt = prompts.read(mode.prompt_family, mode.implementation_prompts[2])
        reporter.stage(mode.label, "PROMPTS", "Loaded implementation prompt set")

        user_prompt = single_stage_prompt_fn(task_prompt, context_prompt, evidence)

        reporter.stage(mode.label, "LLM", "Running implementation model")
        output, err = ai.call(system_prompt, user_prompt, review=False)
        if err:
            reporter.stage(mode.label, "LLM", "Failed")
            return f"MODEL FAILED: {err}"
        reporter.stage(mode.label, "LLM", "Complete")
        reporter.stage(mode.label, "DONE", "Review complete")
        return f"OBSERVE: {evidence}\n\nREVIEW: {output}"

    # ---- TWO-STAGE (Architecture / DevOps style) ----
    reporter.stage(mode.label, "PROMPTS", f"Loading prompt family: {mode.prompt_family}")
    system_prompt = prompts.read(mode.prompt_family, mode.implementation_prompts[0])
    task_prompt = prompts.read(mode.prompt_family, mode.implementation_prompts[1])
    if len(mode.implementation_prompts) >= 3:
        context_prompt = prompts.read(mode.prompt_family, mode.implementation_prompts[2])
        task_prompt = f"{task_prompt}\n\nApplication Context:\n{context_prompt}"
    implementation_user_prompt = implementation_prompt_fn(task_prompt, evidence)
    reporter.stage(mode.label, "PROMPTS", "Loaded implementation prompts")

    reporter.stage(mode.label, "LLM", "Running implementation model")
    implementation_output, err = ai.call(system_prompt, implementation_user_prompt, review=False)
    if err:
        reporter.stage(mode.label, "LLM", "Failed")
        return f"MODEL FAILED: {err}"
    reporter.stage(mode.label, "LLM", "Implementation model complete")

    review_system_prompt = prompts.read(mode.prompt_family, mode.review_prompts[0])
    review_user_prompt = review_prompt_fn(implementation_output, evidence)
    reporter.stage(mode.label, "PROMPTS", "Loaded review prompt")
    reporter.stage(mode.label, "LLM", "Running review model")
    review_output, review_err = ai.call(review_system_prompt, review_user_prompt, review=True)
    if review_err:
        review_output = review_err
        reporter.stage(mode.label, "LLM", "Review model failed")
    else:
        reporter.stage(mode.label, "LLM", "Review model complete")

    reporter.stage(mode.label, "DONE", "Review complete")
    return (
        f"OBSERVE: {evidence}\n\n"
        f"IMPLEMENTATION: {implementation_output}\n"
        f"REVIEW: {review_output}"
    )