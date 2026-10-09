"""Tests for guide OSPF task definitions and property parser fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.evaluator.parsers import ParserRegistry
from benchmark.models.task import PropertyType, TaskDefinition

GUIDE_TASK_IDS = (
    "guide_ospf_multiarea",
    "guide_ospf_redistribution",
    "guide_ospf_troubleshoot",
)

FIXTURES_PATH = (
    Path(__file__).parent.parent.parent
    / "tasks"
    / "archive"
    / "multi_turn"
    / "fixtures"
    / "guide_ospf"
    / "property_outputs.json"
)


@pytest.fixture
def multi_turn_dir() -> Path:
    return Path(__file__).parent.parent.parent / "tasks" / "archive" / "multi_turn"


@pytest.fixture
def property_fixtures() -> dict:
    with FIXTURES_PATH.open() as f:
        return json.load(f)


@pytest.mark.parametrize("task_id", GUIDE_TASK_IDS)
def test_guide_task_loads(multi_turn_dir: Path, task_id: str) -> None:
    path = multi_turn_dir / f"{task_id}.json"
    with path.open() as f:
        task = TaskDefinition.model_validate(json.load(f))
    assert task.task_id == task_id
    assert len(task.intent.properties) >= 4


@pytest.mark.parametrize("task_id", GUIDE_TASK_IDS)
def test_guide_task_property_types_diverse(multi_turn_dir: Path, task_id: str) -> None:
    with (multi_turn_dir / f"{task_id}.json").open() as f:
        task = TaskDefinition.model_validate(json.load(f))
    types = {p.type for p in task.intent.properties}
    assert PropertyType.OSPF_CONFIGURATION in types or PropertyType.ROUTE_EXISTS in types
    assert PropertyType.REACHABILITY in types


@pytest.mark.parametrize("task_id", GUIDE_TASK_IDS)
def test_golden_outputs_satisfy_all_properties(
    multi_turn_dir: Path, property_fixtures: dict, task_id: str
) -> None:
    with (multi_turn_dir / f"{task_id}.json").open() as f:
        task = TaskDefinition.model_validate(json.load(f))
    registry = ParserRegistry()
    golden = property_fixtures[task_id]["golden"]
    for prop in task.intent.properties:
        assert prop.id in golden, f"missing golden fixture for {prop.id}"
        parser = registry.get_parser(prop.evaluation.parser)
        satisfied, _ = parser.parse(golden[prop.id], prop.evaluation.success_condition)
        assert satisfied is True, f"golden output should satisfy {prop.id}"


@pytest.mark.parametrize("task_id", GUIDE_TASK_IDS)
def test_empty_outputs_fail_all_properties(
    multi_turn_dir: Path, property_fixtures: dict, task_id: str
) -> None:
    with (multi_turn_dir / f"{task_id}.json").open() as f:
        task = TaskDefinition.model_validate(json.load(f))
    registry = ParserRegistry()
    empty = property_fixtures[task_id]["empty"]
    for prop in task.intent.properties:
        assert prop.id in empty, f"missing empty fixture for {prop.id}"
        parser = registry.get_parser(prop.evaluation.parser)
        satisfied, _ = parser.parse(empty[prop.id], prop.evaluation.success_condition)
        assert satisfied is False, f"empty output should not satisfy {prop.id}"


def test_troubleshoot_has_fault_verification(multi_turn_dir: Path) -> None:
    with (multi_turn_dir / "guide_ospf_troubleshoot.json").open() as f:
        data = json.load(f)
    assert "preconfiguration" in data
    assert "fault_verification" in data
    assert len(data["fault_verification"]) >= 1
