"""Parse stored run JSON into the config subsequence hat{A}."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Tuple

HatA = List[Tuple[str, str]]

_TYPED_KINDS = {"config", "read"}
_TYPED_STATUS = {"ok", "fail"}


def parse_execution_log_line(entry: str) -> Optional[Tuple[str, str]]:
    """
    Return (node, command) for a config line, or None for a typed read.

    Legacy corpus lines are ``NODE | command``. Current harness lines are
    ``NODE | config|read | command | ok|fail``.
    """
    text = (entry or "").strip()
    if not text:
        return None

    parts = text.split(" | ")
    if (
        len(parts) >= 4
        and parts[1] in _TYPED_KINDS
        and parts[-1] in _TYPED_STATUS
    ):
        if parts[1] == "read":
            return None
        command = " | ".join(parts[2:-1]).strip()
        return parts[0].strip(), command

    node, _, rest = text.partition(" | ")
    if not rest:
        return None
    return node.strip(), rest.strip()


def parse_execution_log(entries: Iterable[str]) -> HatA:
    hat_a: HatA = []
    for entry in entries:
        parsed = parse_execution_log_line(entry)
        if parsed is not None:
            hat_a.append(parsed)
    return hat_a


def parse_full_log_line(entry: str) -> Optional[Tuple[str, str]]:
    """Return (node, command) for every typed line, config and read."""
    text = (entry or "").strip()
    if not text:
        return None

    parts = text.split(" | ")
    if (
        len(parts) >= 4
        and parts[1] in _TYPED_KINDS
        and parts[-1] in _TYPED_STATUS
    ):
        command = " | ".join(parts[2:-1]).strip()
        return parts[0].strip(), command

    node, _, rest = text.partition(" | ")
    if not rest:
        return None
    return node.strip(), rest.strip()


def parse_full_execution_log(entries: Iterable[str]) -> HatA:
    sequence: HatA = []
    for entry in entries:
        parsed = parse_full_log_line(entry)
        if parsed is not None:
            sequence.append(parsed)
    return sequence


def load_hat_a(result: dict[str, Any]) -> HatA:
    return parse_execution_log(result.get("execution_log") or [])


def load_full_sequence(result: dict[str, Any]) -> HatA:
    """Every logged command, in order. The agent label is not a filter."""
    return parse_full_execution_log(result.get("execution_log") or [])


def original_completeness(result: dict[str, Any]) -> Optional[float]:
    scoring = result.get("scoring") or {}
    value = scoring.get("completeness")
    if value is None:
        return None
    return float(value)


def original_satisfied(result: dict[str, Any]) -> List[str]:
    props = result.get("property_results") or []
    return sorted(
        p.get("property_id")
        for p in props
        if p.get("satisfied") and p.get("property_id")
    )


def completeness_agrees(original: float, replays: Sequence[float], tol: float = 1e-9) -> bool:
    if not replays:
        return False
    return all(abs(value - original) <= tol for value in replays)
