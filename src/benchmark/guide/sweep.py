"""Sweep configuration and episode enumeration for the Reveal experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

REVEAL_TASK_FILES = (
    "guide_ospf_redistribution.json",
    "guide_ospf_troubleshoot.json",
)

DEFAULT_MODEL: dict[str, str] = {"provider": "openai", "model": "gpt-5.6-terra"}

DEFAULT_REPEATS = 15


@dataclass(frozen=True)
class RevealEpisode:
    """One episode in the Reveal experiment grid."""

    task_file: Path
    task_id: str
    provider: str
    model: str
    repeat: int

    # Always True — every episode logs passive property snapshots.
    reveal_snapshots: bool = True
    # Agent always runs blind: no oracle tools exposed.
    feedback_arm: str = "blind"

    def testee_id(self) -> str:
        model_slug = self.model.replace("-", "").replace(".", "")
        return f"{self.provider}_{model_slug}_reveal_r{self.repeat}"


def task_paths(tasks_dir: Path) -> list[Path]:
    return [tasks_dir / name for name in REVEAL_TASK_FILES]


def enumerate_episodes(
    tasks_dir: Path,
    model: dict[str, str] = DEFAULT_MODEL,
    repeats: int = DEFAULT_REPEATS,
) -> Iterator[RevealEpisode]:
    """Yield all 30 Reveal episodes (3 tasks × 10 repeats × 1 model)."""
    for task_file in task_paths(tasks_dir):
        task_id = task_file.stem
        for repeat in range(1, repeats + 1):
            yield RevealEpisode(
                task_file=task_file,
                task_id=task_id,
                provider=model["provider"],
                model=model["model"],
                repeat=repeat,
            )


def dry_run_episodes(
    tasks_dir: Path,
    model: dict[str, str] | None = None,
) -> list[RevealEpisode]:
    """One episode per task (3 total) — cheap sanity check before the full run."""
    spec = model or DEFAULT_MODEL
    return [
        RevealEpisode(
            task_file=f,
            task_id=f.stem,
            provider=spec["provider"],
            model=spec["model"],
            repeat=1,
        )
        for f in task_paths(tasks_dir)
    ]


def grid_size(
    repeats: int = DEFAULT_REPEATS,
    n_tasks: int = len(REVEAL_TASK_FILES),
) -> int:
    return n_tasks * repeats


def estimate_wall_hours(episodes: int, minutes_per_episode: float = 25.0) -> float:
    """Rough sequential wall-clock estimate."""
    return episodes * minutes_per_episode / 60.0


def sweep_summary(episodes: list[RevealEpisode]) -> dict[str, Any]:
    """Compute accounting summary for a planned or completed sweep."""
    by_task: dict[str, int] = {}
    by_model: dict[str, int] = {}
    for ep in episodes:
        by_task[ep.task_id] = by_task.get(ep.task_id, 0) + 1
        key = f"{ep.provider}:{ep.model}"
        by_model[key] = by_model.get(key, 0) + 1
    return {
        "total_episodes": len(episodes),
        "by_task": by_task,
        "by_model": by_model,
        "feedback_arm": "blind (all)",
        "reveal_snapshots": "enabled (all)",
        "estimated_wall_hours_sequential": estimate_wall_hours(len(episodes)),
    }
