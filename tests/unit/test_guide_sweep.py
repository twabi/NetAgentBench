"""Tests for the Reveal sweep enumeration (benchmark.guide.sweep)."""

from pathlib import Path

from benchmark.guide.sweep import (
    DEFAULT_MODEL,
    DEFAULT_REPEATS,
    REVEAL_TASK_FILES,
    dry_run_episodes,
    enumerate_episodes,
    grid_size,
)

TASKS_DIR = Path(__file__).parent.parent.parent / "tasks" / "archive" / "multi_turn"


def test_reveal_task_files_exist():
    for name in REVEAL_TASK_FILES:
        assert (TASKS_DIR / name).exists(), name


def test_grid_size_default():
    assert grid_size() == len(REVEAL_TASK_FILES) * DEFAULT_REPEATS


def test_dry_run_one_episode_per_task():
    eps = dry_run_episodes(TASKS_DIR)
    assert len(eps) == len(REVEAL_TASK_FILES)
    assert {e.feedback_arm for e in eps} == {"blind"}
    assert all(e.reveal_snapshots for e in eps)


def test_enumerate_matches_grid_and_model():
    eps = list(enumerate_episodes(TASKS_DIR))
    assert len(eps) == grid_size()
    assert {(e.provider, e.model) for e in eps} == {(DEFAULT_MODEL["provider"], DEFAULT_MODEL["model"])}
    assert len({e.testee_id() for e in eps}) == DEFAULT_REPEATS
