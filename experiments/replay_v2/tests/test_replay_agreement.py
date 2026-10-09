"""Offline tests for replay determinism bookkeeping.

These tests do not start a lab. They check that a stable v2 vector is compared
with the original session, and that a v1 checker error keeps the v2 result.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experiments" / "replay_v2"))

import replay_v2  # noqa: E402


def _result(property_id: str, satisfied: bool):
    return type("R", (), {"property_id": property_id, "satisfied": satisfied})()


class _Task:
    def __init__(self, properties):
        self.intent = type("I", (), {"properties": properties})()


class _Evaluator:
    def __init__(self, fail_on):
        self.fail_on = fail_on
        self.calls = []

    def evaluate_all_properties(self, infrastructure, topology_id, properties):
        self.calls.append(list(properties))
        if properties == self.fail_on:
            raise RuntimeError("v1 checker failed")
        return [_result(p, p.endswith("_ok")) for p in properties]


def test_original_vector_reads_property_results():
    data = {
        "property_results": [
            {"property_id": "rip_enabled", "satisfied": True},
            {"property_id": "loopback_reachability", "satisfied": False},
        ]
    }
    assert replay_v2.original_v2_vector(data) == {
        "rip_enabled": True,
        "loopback_reachability": False,
    }


def test_stable_vector_matches_original():
    original = {"a": True, "b": False}
    replay = {
        "v2_vector": {"a": True, "b": False},
        "v2_completeness": 0.5,
        "v1_vector": {"x": True},
        "v1_completeness": 1.0,
    }
    rec = replay_v2.summarize_replays([replay, replay], repeats=2, original_vector=original)
    assert rec["stable_v2_vector"] is True
    assert rec["matches_original_v2"] is True
    assert rec["v2_vector"] == original


def test_stable_vector_that_differs_from_original_is_reported():
    original = {"a": True, "b": True}
    replay = {
        "v2_vector": {"a": True, "b": False},
        "v2_completeness": 0.5,
        "v1_vector": {"x": False},
        "v1_completeness": 0.0,
    }
    rec = replay_v2.summarize_replays([replay, replay], repeats=2, original_vector=original)
    assert rec["stable_v2_vector"] is True
    assert rec["matches_original_v2"] is False


def test_unstable_replays_do_not_match_original():
    original = {"a": True}
    first = {"v2_vector": {"a": True}, "v2_completeness": 1.0, "v1_vector": {"x": True}, "v1_completeness": 1.0}
    second = {"v2_vector": {"a": False}, "v2_completeness": 0.0, "v1_vector": {"x": True}, "v1_completeness": 1.0}
    rec = replay_v2.summarize_replays([first, second], repeats=2, original_vector=original)
    assert rec["stable_v2_vector"] is False
    assert rec["matches_original_v2"] is False


def test_v1_error_keeps_the_v2_replay():
    evaluator = _Evaluator(fail_on=["old_check"])
    scored = replay_v2.score_terminal(
        evaluator, infrastructure=None, topology_id="topo",
        task_v2=_Task(["new_ok", "new_bad"]),
        task_v1=_Task(["old_check"]),
    )
    assert scored["v2_vector"] == {"new_ok": True, "new_bad": False}
    assert scored["v1_vector"] is None
    assert "v1 checker failed" in scored["v1_error"]
    assert evaluator.calls == [["new_ok", "new_bad"], ["old_check"]]

    rec = replay_v2.summarize_replays([scored, scored, scored], repeats=3, original_vector=scored["v2_vector"])
    assert rec["n_replays_ok"] == 3
    assert rec["stable_v2_vector"] is True
    assert rec["stable_v1_vector"] is False
    assert rec["matches_original_v2"] is True
    assert "error" not in scored
