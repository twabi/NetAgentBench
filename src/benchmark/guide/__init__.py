"""Property-guidance experiment: arms, prompts, and task sanitization."""

from benchmark.guide.arms import FeedbackArm, CHECK_PROPERTIES_CAP
from benchmark.guide.prompts import (
    build_benchmark_instructions,
    build_system_prompt,
    format_declared_properties_block,
    sanitize_task_context_for_arm,
)
from benchmark.guide.sweep import (
    REVEAL_TASK_FILES,
    RevealEpisode,
    dry_run_episodes,
    enumerate_episodes,
    grid_size,
    sweep_summary,
)

__all__ = [
    "FeedbackArm",
    "CHECK_PROPERTIES_CAP",
    "build_benchmark_instructions",
    "build_system_prompt",
    "format_declared_properties_block",
    "sanitize_task_context_for_arm",
    "REVEAL_TASK_FILES",
    "RevealEpisode",
    "dry_run_episodes",
    "enumerate_episodes",
    "grid_size",
    "sweep_summary",
]
