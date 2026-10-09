"""Helpers for live property and syntactic validity checks."""

from __future__ import annotations

from typing import Any

from benchmark.models.results import PropertyEvaluationResult
from benchmark.scoring.metrics import ScoringCalculator


def build_property_check_response(
    property_results: list[PropertyEvaluationResult],
    check_index: int,
    cap: int,
) -> dict[str, Any]:
    """Format check_properties tool output from evaluation results."""
    vector = {r.property_id: r.satisfied for r in property_results}
    completeness = ScoringCalculator().compute_completeness(property_results)
    return {
        "success": True,
        "properties": vector,
        "completeness": completeness,
        "check_index": check_index,
        "cap": cap,
        "satisfied_count": sum(1 for r in property_results if r.satisfied),
        "total_properties": len(property_results),
    }


def build_syntactic_validity_response(
    execution_results: list[tuple[str, str, bool]],
    check_index: int,
    cap: int,
    window: int = 10,
) -> dict[str, Any]:
    """Format check_syntactic_validity (placebo) tool output."""
    recent = execution_results[-window:] if execution_results else []
    if not recent:
        return {
            "success": True,
            "signal_type": "syntactic_validity",
            "commands_checked": 0,
            "successful_commands": 0,
            "success_rate": 1.0,
            "check_index": check_index,
            "cap": cap,
            "note": "No commands executed yet; success_rate defaults to 1.0",
        }

    successes = sum(1 for _, _, ok in recent if ok)
    rate = successes / len(recent)
    return {
        "success": True,
        "signal_type": "syntactic_validity",
        "commands_checked": len(recent),
        "successful_commands": successes,
        "success_rate": rate,
        "check_index": check_index,
        "cap": cap,
        "recent_failures": [
            {"node": node, "command": cmd}
            for node, cmd, ok in recent
            if not ok
        ][:5],
    }
