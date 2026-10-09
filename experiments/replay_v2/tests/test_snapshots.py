"""Snapshot-to-command alignment for both harness snapshot policies."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import snapshots  # noqa: E402
from snapshots import aligned, last_write_before, run_snapshot_mode, set_cohort_mode  # noqa: E402


def classify(cmd):
    return "read" if cmd.startswith("show") else "write"


def snap(c):
    return {"kind": "passive_reveal", "properties": {"p": c >= 1.0}, "completeness": c}


def run(commands, snaps):
    return {
        "command_transcript": [{"node": "r1", "command": c, "command_type": t} for c, t in commands],
        "metrics": {"property_trajectory": snaps},
    }


# show (read), conf A (config), show labelled config (phantom), conf B sent as read (hidden)
CMDS = [("show ip route", "read"), ("conf A", "config"), ("show run", "config"), ("conf B", "read")]


def teardown_function(_):
    snapshots._COHORT_MODE = None


def test_labelled_mode_maps_to_config_labelled_commands():
    d = run(CMDS, [snap(0.0), snap(0.0)])
    assert run_snapshot_mode(d) == "labelled"
    al = aligned(d, classify)
    assert [a["cmd_index"] for a in al] == [1, 2]
    assert [a["kind"] for a in al] == ["write", "read"]


def test_all_mode_maps_one_snapshot_per_command():
    d = run(CMDS, [snap(0.0), snap(0.0), snap(0.0), snap(1.0)])
    assert run_snapshot_mode(d) == "all"
    al = aligned(d, classify)
    assert [a["cmd_index"] for a in al] == [0, 1, 2, 3]
    assert al[3]["kind"] == "write"  # hidden write is observed in 'all' mode


def test_cohort_mode_overrides_ambiguous_run():
    # every command labelled config: one snapshot per command under either harness
    ambiguous = run([("conf A", "config"), ("show run", "config")], [snap(0.0), snap(1.0)])
    labelled = run(CMDS, [snap(0.0), snap(0.0)])
    assert run_snapshot_mode(ambiguous) == "all"
    assert set_cohort_mode([ambiguous, labelled]) == "labelled"
    assert snapshots.snapshot_mode(ambiguous) == "labelled"
    # the alignment itself is the same either way
    assert [a["cmd_index"] for a in aligned(ambiguous, classify)] == [0, 1]
    assert set_cohort_mode([ambiguous]) == "all"


def test_last_write_before_skips_reads():
    d = run(CMDS, [])
    assert last_write_before(d, 2, classify)[0] == 1
    assert last_write_before(d, 0, classify) == (None, None)
    assert last_write_before(d, 3, classify)[0] == 3
