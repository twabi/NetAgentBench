"""Offline tests for the v2 intent properties.

Fixtures are real FRR 8.4 outputs captured by instrument_check.py at every stage of the
reference solutions (tests/fixtures/v2_observations.json), so these tests need no lab.
Negative cases are derived from those real outputs by minimal edits that reproduce
failure modes seen in the logged runs (faulted baseline, default RIP banner, locally
originated prefixes, gaming of string checks).

Run:  pytest experiments/replay_v2/tests -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
V2 = REPO / "tasks" / "multi_turn_v2"
FIX = HERE / "fixtures" / "v2_observations.json"

import sys  # noqa: E402

sys.path.insert(0, str(REPO / "src"))
from benchmark.evaluator.parsers import ParserRegistry  # noqa: E402

PROPS = {
    p["id"]: p
    for f in sorted(V2.glob("*.json"))
    for p in json.loads(f.read_text())["intent"]["properties"]
}


def ev(pid: str, output: str) -> bool:
    spec = PROPS[pid]["evaluation"]
    ok, _ = ParserRegistry().get_parser(spec["parser"]).parse(output, spec["success_condition"])
    return ok


def fixtures():
    data = json.loads(FIX.read_text())
    for rec in data:
        for stage in rec["stages"]:
            for pid, raw in stage["observations"].items():
                idx = rec["properties"].index(pid)
                yield pytest.param(pid, raw, stage["expected"][idx] == "T",
                                   id=f"{rec['task_id']}|{rec['scenario']}|{stage['stage'][:30]}|{pid}")


def obs(task_id: str, stage_prefix: str, pid: str, scenario: str = "reference") -> str:
    if not FIX.exists():
        pytest.skip("fixtures not captured yet")
    for rec in json.loads(FIX.read_text()):
        if rec["task_id"] == task_id and rec["scenario"] == scenario:
            for st in rec["stages"]:
                if st["stage"].startswith(stage_prefix):
                    return st["observations"][pid]
    raise KeyError((task_id, stage_prefix, pid))


# ---------------------------------------------------------------- captured outputs
@pytest.mark.skipif(not FIX.exists(), reason="run instrument_check.py and extract fixtures first")
@pytest.mark.parametrize("pid,raw,expected", list(fixtures()) if FIX.exists() else [])
def test_captured_outputs(pid, raw, expected):
    assert ev(pid, raw) is expected


# ---------------------------------------------------------------- hand-checked cases
RIP_DEFAULT_BANNER = (
    'Routing Protocol is "rip"\n'
    "  Default version control: send version 2, receive any version \n"
)


def test_rip_default_banner_is_not_v2():
    assert ev("rip_enabled", RIP_DEFAULT_BANNER)
    assert not ev("ripv2_enforced", RIP_DEFAULT_BANNER)


def test_rip_not_running():
    assert not ev("rip_enabled", "% RIP instance not found\n")


@pytest.mark.parametrize("line,ok", [
    ("3 packets transmitted, 3 packets received, 0% packet loss", True),   # busybox
    ("3 packets transmitted, 3 received, 0% packet loss, time 2055ms", True),  # iputils
    ("3 packets transmitted, 2 packets received, 33% packet loss", False),
    ("3 packets transmitted, 0 packets received, 100% packet loss", False),
    ("ping: bind: Cannot assign requested address", False),
])
def test_ping_formats(line, ok):
    assert ev("loopback_reachability", line) is ok


# OSPF troubleshooting: the faulted baseline observed on the original substrate
TS_R2_NBRS_FAULTED = (
    "\nNeighbor ID     Pri State           Up Time         Dead Time Address         Interface"
    "                        RXmtL RqstL DBsmL\n"
    "10.0.0.1          1 Full/Backup     1m50s             39.457s 10.0.12.1       eth1:10.0.12.2"
    "                       0     0     0\n"
)
TS_R3_ETH1_FAULTED = (
    "eth1 is up\n  Internet Address 10.0.23.2/30, Broadcast 10.0.23.3, Area 0.0.0.1\n"
)


def test_ts_faulted_baseline_is_all_false():
    assert not ev("r2_r3_adjacency_full", TS_R2_NBRS_FAULTED)
    assert not ev("fault_corrected", TS_R3_ETH1_FAULTED)
    assert not ev("fault_corrected", "% OSPF is not enabled in vrf default\n")
    assert not ev("r2_r3_adjacency_full", "% OSPF is not enabled in vrf default\n")


def test_ts_adjacency_must_be_full_not_init():
    init = TS_R2_NBRS_FAULTED + "10.0.0.3          1 Init/DROther    5s   35s 10.0.23.2  eth2:10.0.23.1  0 0 0\n"
    full = TS_R2_NBRS_FAULTED + "10.0.0.3          1 Full/DR         5s   35s 10.0.23.2  eth2:10.0.23.1  0 0 0\n"
    assert not ev("r2_r3_adjacency_full", init)
    assert ev("r2_r3_adjacency_full", full)


def test_ts_area_1_0_0_0_is_not_backbone():
    # guard against a pattern that would also match 'Area 0.0.0.01' style strings
    assert not ev("fault_corrected", "Internet Address 10.0.23.2/30, Area 0.0.0.10\n")


# BGP: negatives derived from captured positives
def test_bgp_session_configured_but_not_established():
    raw = obs("ccie_bgp_dual_homing_expert", "reference", "ebgp_isp1_established")
    idle = re.sub(r"BGP state = Established[^\n]*", "BGP state = Active", raw)
    assert ev("ebgp_isp1_established", raw)
    assert not ev("ebgp_isp1_established", idle)


def test_bgp_hold_time_thresholds():
    raw = obs("ccie_bgp_dual_homing_expert", "reference", "fast_failover_timers")
    assert ev("fast_failover_timers", raw)
    for hold in ("180", "90", "60", "300"):
        assert not ev("fast_failover_timers", re.sub(r"Hold time is \d+", f"Hold time is {hold}", raw))


def test_bgp_locally_originated_prefix_does_not_count_as_advertised():
    raw = obs("ccie_bgp_dual_homing_expert", "outbound prefix-list", "outbound_filtering")
    assert ev("outbound_filtering", raw)
    # the logged gaming run: ISP1 originates the enterprise prefix itself (empty AS path)
    local = re.sub(r"(10\.0\.0\.0/8\s+)203\.0\.113\.2(\s[^\n]*?)\d+(?: \d+)* i$",
                   r"\g<1>0.0.0.0\g<2>i", raw, flags=re.M)
    assert local != raw
    assert not ev("outbound_filtering", local)


def test_bgp_leak_breaks_outbound_filtering():
    raw = obs("ccie_bgp_dual_homing_expert", "EDGE1 advertises 10/8 but also leaks", "outbound_filtering")
    assert "203.0.113.0/30" in raw
    assert not ev("outbound_filtering", raw)


def test_bgp_local_pref_must_be_raised_on_isp1_routes():
    raw = obs("ccie_bgp_dual_homing_expert", "local-preference", "primary_path_preference")
    assert ev("primary_path_preference", raw)
    assert not ev("primary_path_preference", re.sub(r'"locPrf":\s*200', '"locPrf":100', raw))


def test_bgp_prepend_needs_repeated_as():
    raw = obs("ccie_bgp_dual_homing_expert", "EDGE2 advertises", "as_path_prepending")
    assert ev("as_path_prepending", raw)
    single = re.sub(r"(\d+)(?: \1)+ i$", r"\1 i", raw, flags=re.M)
    assert single != raw
    assert not ev("as_path_prepending", single)


LEAKED_BGP_TABLE = """\
   Network          Next Hop            Metric LocPrf Weight Path
*> 1.1.1.1/32       0.0.0.0                  0         32768 i
*> 10.0.0.1/32      203.0.113.2              0             0 65000 i
*> 10.1.0.0/30      203.0.113.2              0             0 65000 i
*> 192.0.2.0/24     203.0.113.2              0             0 65000 i
"""

FILTERED_BGP_TABLE = """\
   Network          Next Hop            Metric LocPrf Weight Path
*> 1.1.1.1/32       0.0.0.0                  0         32768 i
*> 192.0.2.0/24     203.0.113.2              0             0 65000 i
"""

ADVERTISED_ONLY = """\
   Network          Next Hop            Metric LocPrf Weight Path
*> 192.0.2.0/24     0.0.0.0                  0         32768 i
"""
ADVERTISED_LEAK = ADVERTISED_ONLY + "*> 10.0.0.1/32      0.0.0.0                  0         32768 i\n"


def test_route_filter_is_false_while_the_leak_is_present():
    assert not ev("isp_receives_authorized_only", LEAKED_BGP_TABLE)
    assert ev("isp_receives_authorized_only", FILTERED_BGP_TABLE)
    peering = FILTERED_BGP_TABLE + "*> 203.0.113.0/30   203.0.113.2              0             0 65000 i\n"
    assert not ev("isp_receives_authorized_only", peering)


def test_route_filter_counts_advertised_prefixes_not_the_route_map_name():
    assert ev("filter_applied_outbound", ADVERTISED_ONLY)
    assert not ev("filter_applied_outbound", ADVERTISED_LEAK)
    assert not ev("filter_applied_outbound", "Route map for outgoing advertisements is *FILTER-OUT\n")


def test_bgp_task_text_pins_the_design_the_checker_accepts():
    task = json.loads((V2 / "ccie_bgp_dual_homing_expert.json").read_text())
    text = task["description"]
    assert "65100" in text
    assert "10.0.0.0/8" in text
    assert "local preference above 100" in text
    assert "ISP1" in text
    assert "65001" in text


# multi-area: 'O IA' never appears in FRR's 'show ip route'; summaries live in 'show ip ospf route'
def test_ma_summary_requires_suppression_of_component():
    raw = obs("ccnp_multiarea_ospf_intermediate", "reference", "area1_summarized")
    assert ev("area1_summarized", raw)
    leaky = raw + "N IA 10.1.24.0/30         [20] area: 0.0.0.0\n"
    assert not ev("area1_summarized", leaky)
