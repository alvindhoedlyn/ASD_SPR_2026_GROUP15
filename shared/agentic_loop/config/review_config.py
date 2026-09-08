"""
SHARED mode configuration shape. This dataclass has no knowledge of any
specific student's service — each student writes their own
build_mode_config() (in their own agentic_loop/config/review_config.py)
that returns a dict of these, pointed at their own collectors and prompts.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

CollectFn = Callable[..., tuple[bool, str]]
BuildPromptFn = Callable[..., str]


@dataclass(frozen=True)
class ModeConfig:
    key: str
    label: str
    prompt_family: str
    implementation_prompts: tuple[str, ...]
    review_prompts: tuple[str, ...] = ()
    two_stage: bool = False 