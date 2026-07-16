"""Tests for equal-weight macro pooling (model / grid / protocol)."""

import pytest

from scripts.macro_pooled_stats import (
    grid_macro,
    model_macro,
    protocol_macro,
    run_weighted,
)


def _p(model: str, task_id: str, score: float, succ: float, melt: float) -> dict:
    return {
        "model": model,
        "task_id": task_id,
        "final_score": score,
        "success": bool(succ),
        "meltdown": bool(melt),
        "turns": 1.0,
        "total_tokens": 100.0,
        "score_per_1k_tokens": score * 10,
    }


def test_run_vs_model_vs_grid_macro_differ_with_imbalance():
    """
    Model A: task1 three 1s, task2 two 0s. Model B: task1 one 0, task2 two 1s.
    Run-weighted, model-macro, and grid-macro must split as expected.
    """
    profiles = [_p("A", "ccna_rip_routing_basic", 1, 1, 0) for _ in range(3)]
    profiles += [_p("A", "ccnp_multiarea_ospf_intermediate", 0, 0, 0) for _ in range(2)]
    profiles += [_p("B", "ccna_rip_routing_basic", 0, 0, 0)]
    profiles += [_p("B", "ccnp_multiarea_ospf_intermediate", 1, 1, 0) for _ in range(2)]

    rw = run_weighted(profiles)["mean_final_score"]
    mm = model_macro(profiles)["mean_final_score"]
    gm = grid_macro(profiles)["mean_final_score"]

    # A mean = 3/5, B mean = 2/3
    assert rw == pytest.approx((3.0 + 0 + 0 + 2.0) / 8.0)
    assert mm == pytest.approx((3.0 / 5.0 + 2.0 / 3.0) / 2.0)
    # cells: A×RIP=1, A×OSPF=0, B×RIP=0, B×OSPF=1
    assert gm == pytest.approx(0.5)


def test_protocol_macro_equalizes_protocol_groups():
    """Two protocols with different cell means; protocol_macro is mean of group means."""
    profiles = [
        _p("A", "ccna_rip_routing_basic", 1.0, 1, 0),
        _p("B", "ccna_rip_routing_basic", 0.0, 0, 0),
        _p("A", "ccnp_multiarea_ospf_intermediate", 0.0, 0, 0),
        _p("B", "ccnp_multiarea_ospf_intermediate", 0.0, 0, 0),
    ]
    pm = protocol_macro(profiles)["mean_final_score"]
    # RIP group cell means 1 and 0 -> 0.5; OSPF group 0 and 0 -> 0; protocol_macro -> 0.25
    assert pm == pytest.approx(0.25)


def test_empty_profiles():
    assert run_weighted([]) == {}
    assert model_macro([]) == {}
    assert grid_macro([]) == {}
    assert protocol_macro([]) == {}
