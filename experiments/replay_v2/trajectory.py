"""Classify how a property vector changes after each configuration command.

A snapshot is one entry of metrics.property_trajectory: a turn number and the
boolean vector recorded after that configuration command.
"""

from __future__ import annotations

from typing import Any


def _properties(snapshot: dict[str, Any]) -> dict[str, bool]:
    raw = snapshot.get("properties") or {}
    return {str(key): bool(value) for key, value in raw.items()}


def classify_trajectory(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Mark first-true turns, unchanged commands, and drops that later return.

    The first snapshot has no predecessor, so it is never counted as unchanged.
    A command can both satisfy a property for the first time and drop another.
    """
    ordered = list(snapshots)
    if not ordered:
        return {
            "n_commands": 0,
            "first_true": {},
            "never_true": [],
            "unchanged_turns": [],
            "drops_that_return": [],
            "drops_that_stay": [],
            "first_satisfy_turns": [],
            "drop_return_turns": [],
        }

    keys: list[str] = []
    for snapshot in ordered:
        for key in _properties(snapshot):
            if key not in keys:
                keys.append(key)

    first_true: dict[str, int] = {}
    for snapshot in ordered:
        turn = int(snapshot["turn"])
        for key, value in _properties(snapshot).items():
            if value and key not in first_true:
                first_true[key] = turn

    unchanged: list[int] = []
    drops: list[tuple[str, int]] = []
    for previous, current in zip(ordered, ordered[1:]):
        prev = _properties(previous)
        cur = _properties(current)
        turn = int(current["turn"])
        if all(prev.get(key, False) == cur.get(key, False) for key in keys):
            unchanged.append(turn)
        for key in keys:
            if prev.get(key, False) and not cur.get(key, False):
                drops.append((key, turn))

    returning: list[dict[str, Any]] = []
    staying: list[dict[str, Any]] = []
    for key, turn in drops:
        later = [
            int(snapshot["turn"])
            for snapshot in ordered
            if int(snapshot["turn"]) > turn and _properties(snapshot).get(key, False)
        ]
        if later:
            returning.append({"property": key, "drop_turn": turn, "return_turn": later[0]})
        else:
            staying.append({"property": key, "drop_turn": turn})

    return {
        "n_commands": len(ordered),
        "first_true": first_true,
        "never_true": [key for key in keys if key not in first_true],
        "unchanged_turns": unchanged,
        "drops_that_return": returning,
        "drops_that_stay": staying,
        "first_satisfy_turns": sorted(set(first_true.values())),
        "drop_return_turns": sorted({item["drop_turn"] for item in returning}),
    }


def event_shares(classified: dict[str, Any]) -> dict[str, float]:
    """Share of configuration commands in each role. Roles may overlap."""
    n = int(classified["n_commands"])
    if n == 0:
        return {"first_satisfy": 0.0, "unchanged": 0.0, "drop_returns": 0.0}
    return {
        "first_satisfy": len(classified["first_satisfy_turns"]) / n,
        "unchanged": len(classified["unchanged_turns"]) / n,
        "drop_returns": len(classified["drop_return_turns"]) / n,
    }
