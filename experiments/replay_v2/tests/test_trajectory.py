"""Offline tests for property-trajectory event classification."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from trajectory import classify_trajectory, event_shares  # noqa: E402


def _snap(turn: int, **properties: bool) -> dict:
    return {"turn": turn, "properties": properties, "completeness": 0.0}


def test_empty_trajectory():
    classified = classify_trajectory([])
    assert classified["n_commands"] == 0
    assert classified["first_true"] == {}
    assert event_shares(classified) == {
        "first_satisfy": 0.0,
        "unchanged": 0.0,
        "drop_returns": 0.0,
    }


def test_first_true_unchanged_and_a_drop_that_returns():
    classified = classify_trajectory([
        _snap(1, a=False, b=False),
        _snap(2, a=True, b=False),
        _snap(3, a=True, b=False),
        _snap(4, a=False, b=True),
        _snap(5, a=True, b=True),
    ])
    assert classified["first_true"] == {"a": 2, "b": 4}
    assert classified["never_true"] == []
    assert classified["unchanged_turns"] == [3]
    assert classified["drops_that_return"] == [
        {"property": "a", "drop_turn": 4, "return_turn": 5}
    ]
    assert classified["drops_that_stay"] == []
    shares = event_shares(classified)
    assert shares["first_satisfy"] == 2 / 5
    assert shares["unchanged"] == 1 / 5
    assert shares["drop_returns"] == 1 / 5


def test_drop_that_never_returns_and_first_command_can_satisfy():
    classified = classify_trajectory([
        _snap(1, a=True, b=False),
        _snap(2, a=False, b=False),
    ])
    assert classified["first_true"] == {"a": 1}
    assert classified["never_true"] == ["b"]
    assert classified["unchanged_turns"] == []
    assert classified["drops_that_stay"] == [{"property": "a", "drop_turn": 2}]
    assert classified["drops_that_return"] == []
    assert event_shares(classified)["first_satisfy"] == 0.5
