import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parse_log import (
    completeness_agrees,
    load_hat_a,
    original_completeness,
    parse_execution_log,
)


def test_parse_legacy_config_line_splits_on_first_separator():
    entries = [
        "R1 | bash -lc \"ip addr add 10.1.1.1/30 dev eth1\"",
        "R2 | sysctl -w net.ipv4.ip_forward=1",
    ]
    assert parse_execution_log(entries) == [
        ("R1", 'bash -lc "ip addr add 10.1.1.1/30 dev eth1"'),
        ("R2", "sysctl -w net.ipv4.ip_forward=1"),
    ]


def test_parse_full_execution_log_keeps_reads_and_config():
    from parse_log import load_full_sequence, parse_full_execution_log

    entries = [
        "R1 | config | ip addr add 10.0.0.1/32 dev lo | ok",
        "R1 | read | show ip route | ok",
        "R2 | config | router ospf | fail",
    ]
    expected = [
        ("R1", "ip addr add 10.0.0.1/32 dev lo"),
        ("R1", "show ip route"),
        ("R2", "router ospf"),
    ]
    assert parse_full_execution_log(entries) == expected
    assert load_full_sequence({"execution_log": entries}) == expected


def test_parse_typed_log_drops_reads_and_keeps_config():
    entries = [
        "R1 | config | ip addr add 10.0.0.1/32 dev lo | ok",
        "R1 | read | show ip route | ok",
        "R2 | config | router ospf | fail",
    ]
    assert parse_execution_log(entries) == [
        ("R1", "ip addr add 10.0.0.1/32 dev lo"),
        ("R2", "router ospf"),
    ]


def test_load_hat_a_uses_execution_log_from_result_json():
    result = {
        "scoring": {"completeness": 0.5},
        "execution_log": [
            "R1 | ip addr add 10.0.0.1/32 dev lo",
            "R1 | show ip route",
        ],
    }
    assert load_hat_a(result) == [
        ("R1", "ip addr add 10.0.0.1/32 dev lo"),
        ("R1", "show ip route"),
    ]
    assert original_completeness(result) == 0.5


def test_completeness_agrees_when_all_replays_match_original():
    assert completeness_agrees(0.5, [0.5, 0.5, 0.5]) is True


def test_completeness_agrees_false_on_mismatch():
    assert completeness_agrees(1.0, [1.0, 0.75, 1.0]) is False


def test_selected_traces_have_nonempty_config_logs():
    import json

    repo = Path(__file__).resolve().parents[3]
    spec = json.loads((Path(__file__).resolve().parents[1] / "traces.json").read_text())
    assert spec["repeats"] == 3
    assert len(spec["traces"]) == 3
    for trace in spec["traces"]:
        result = json.loads((repo / trace["run_json"]).read_text())
        hat_a = load_hat_a(result)
        assert hat_a, trace["id"]
        assert original_completeness(result) is not None
