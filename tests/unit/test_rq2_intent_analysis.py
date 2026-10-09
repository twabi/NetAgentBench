"""Unit tests for the RQ2 intent-resolution experiment."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "experiments" / "rq2_intent_resolution"
sys.path.insert(0, str(EXP_DIR))

from analyze import (
    PREREQUISITES,
    classify_run,
    completeness_from_properties,
    infer_pattern,
    is_single_agent_run,
    property_rates,
    prerequisite_stats,
    summarize_resolution,
)


def _run(task_id, props, run_id="x_single_mt_1"):
    return {
        "run_id": run_id,
        "task_id": task_id,
        "property_results": [
            {"property_id": pid, "satisfied": sat} for pid, sat in props
        ],
    }


def test_completeness_is_fraction_of_satisfied_properties():
    props = [
        {"property_id": "a", "satisfied": True},
        {"property_id": "b", "satisfied": False},
        {"property_id": "c", "satisfied": True},
    ]
    assert completeness_from_properties(props) == pytest.approx(2 / 3)


def test_completeness_empty_properties_is_zero():
    assert completeness_from_properties([]) == 0.0


def test_classify_run_complete_when_all_properties_hold():
    assert classify_run(_run("t", [("a", True), ("b", True)])) == "complete"


def test_classify_run_partial_when_some_properties_hold():
    assert classify_run(_run("t", [("a", True), ("b", False)])) == "partial"


def test_classify_run_zero_when_no_properties_hold():
    assert classify_run(_run("t", [("a", False), ("b", False)])) == "zero"


def test_summarize_resolution_counts_complete_partial_zero_per_task():
    runs = [
        _run("rip", [("p1", True), ("p2", True)]),
        _run("rip", [("p1", True), ("p2", False)]),
        _run("rip", [("p1", False), ("p2", False)]),
        _run("ospf", [("q", True)]),
    ]
    summary = summarize_resolution(runs)
    assert summary["rip"] == {"n": 3, "complete": 1, "partial": 1, "zero": 1}
    assert summary["ospf"] == {"n": 1, "complete": 1, "partial": 0, "zero": 0}


def test_property_rates_report_satisfaction_fractions():
    runs = [
        _run("rip", [("proc", True), ("reach", False)]),
        _run("rip", [("proc", True), ("reach", True)]),
    ]
    rates = {row["property_id"]: row for row in property_rates(runs, "rip")}
    assert rates["proc"]["satisfied"] == 2
    assert rates["proc"]["n"] == 2
    assert rates["reach"]["rate"] == pytest.approx(0.5)


def test_prerequisite_stats_count_necessity_violations():
    runs = [
        _run("rip", [("up", True), ("down", True)]),
        _run("rip", [("up", False), ("down", True)]),
        _run("rip", [("up", True), ("down", False)]),
    ]
    stats = prerequisite_stats(runs, [("up", "down")])
    row = stats[0]
    assert row["n_upstream_true"] == 2
    assert row["n_downstream_true"] == 2
    assert row["necessity_violations"] == 1
    assert row["necessity_holds"] is False
    assert row["p_up_given_down"] == pytest.approx(0.5)


def test_prerequisite_stats_necessity_holds_when_downstream_implies_upstream():
    runs = [
        _run("rip", [("up", True), ("down", True)]),
        _run("rip", [("up", True), ("down", False)]),
        _run("rip", [("up", False), ("down", False)]),
    ]
    stats = prerequisite_stats(runs, [("up", "down")])
    assert stats[0]["necessity_violations"] == 0
    assert stats[0]["necessity_holds"] is True
    assert stats[0]["p_up_given_down"] == pytest.approx(1.0)


def test_bgp_filtering_has_no_declared_prerequisites():
    assert "troubleshoot_bgp_route_filtering" not in PREREQUISITES


def test_area1_routes_not_treated_as_prerequisite_of_reachability():
    edges = PREREQUISITES["ccnp_multiarea_ospf_intermediate"]
    assert ("area1_routes_visible", "end_to_end_reachability") not in edges


def test_infer_pattern_from_run_id():
    assert infer_pattern("openai_gpt5mini_single_mt_20260225_1") == "single"
    assert infer_pattern("ollama_qwen_multi_sequential_mt_1") == "sequential"


def test_is_single_agent_run_excludes_multi_patterns():
    assert is_single_agent_run({"run_id": "m_single_mt_1", "testee_id": "x_single"})
    assert not is_single_agent_run(
        {"run_id": "m_multi_sequential_mt_1", "testee_id": "x_multi_sequential"}
    )
