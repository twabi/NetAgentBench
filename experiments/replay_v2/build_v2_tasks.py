"""Build corrected (v2) task files from the originals in tasks/multi_turn/.

Design rules for every intent property:
  R1  False on the task's baseline state (after preconfiguration, converged).
  R2  Tests the state named in its description, not an incidental string.
  R3  Accepts alternative valid configurations where the task text allows them.
  R4  Robust to FRR 8.x vs 10.x and to busybox vs iputils ping output.

What changed per task is recorded in CHANGES below and written to
tasks/multi_turn_v2/CHANGES.md.

Usage:  python build_v2_tasks.py            (writes tasks/multi_turn_v2/*.json)
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "tasks" / "multi_turn"
DST = REPO / "tasks" / "multi_turn_v2"

# busybox ping (frr image): "3 packets transmitted, 3 packets received"
# iputils ping (Ubuntu):    "3 packets transmitted, 3 received"
PING_OK = r"3 packets transmitted, 3 (?:packets )?received"


def rx(pid, ptype, desc, node, cmd, pattern, must_match=True, ci=False):
    cond = {"pattern": pattern, "must_match": must_match}
    if ci:
        cond["case_insensitive"] = True
    return {
        "id": pid,
        "type": ptype,
        "description": desc,
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": node,
            "command": cmd,
            "parser": "regex",
            "success_condition": cond,
        },
    }


def nbr_full(rid):
    """FRR 'show ip ospf neighbor' row for router-id `rid` in state Full."""
    return rf"^{re.escape(rid)}\s+\d+\s+Full/"


def ping(node, src, dst):
    return f"ping -c 3 -W 2 -I {src} {dst}"


CHANGES: dict[str, list[str]] = {}

# ---------------------------------------------------------------------------
# RIP (addressing plan is valid; description unchanged so logged runs replay)
# ---------------------------------------------------------------------------
def rip(t):
    t["intent"]["properties"] = [
        rx("rip_enabled", "interface_up", "RIP routing process is running on R1",
           "R1", "vtysh -c 'show ip rip status'", r'Routing Protocol is "rip"'),
        rx("ripv2_enforced", "interface_up",
           "RIP version 2 is configured explicitly (FRR's default sends v2 but accepts v1)",
           "R1", "vtysh -c 'show ip rip status'",
           r"send version 2, receive version 2"),
        rx("rip_authentication", "interface_up",
           "RIP authentication is enabled on both of R1's router-facing links",
           "R1", "vtysh -c 'show running-config'",
           r"\A(?=.*^interface eth1\n(?:[ \t][^\n]*\n)*?[ \t]+ip rip authentication (?:mode|string))"
           r"(?=.*^interface eth2\n(?:[ \t][^\n]*\n)*?[ \t]+ip rip authentication (?:mode|string))"),
        rx("r4_loopback_via_rip", "route_exists",
           "R1 has selected a RIP-learned route to R4's loopback 10.0.0.4/32",
           "R1", "vtysh -c 'show ip route 10.0.0.4/32'", r'Known via "rip"[^\n]*best'),
        rx("loopback_reachability", "reachability",
           "End-to-end reachability: R1's loopback reaches R4's loopback",
           "R1", ping("R1", "10.0.0.1", "10.0.0.4"), PING_OK),
    ]
    CHANGES[t["task_id"]] = [
        "ripv2_configured matched FRR's default banner 'send version 2, receive any version', "
        "so it was true whenever RIP ran. Now requires 'receive version 2' (explicit `version 2`).",
        "rip_routes_learned matched any 'R>' route. Now requires a selected RIP route to R4's loopback.",
        "Added rip_authentication: the task text asks for authentication but nothing checked it. "
        "It reads R1's running config (FRR exposes no other auth state); accepts md5 or simple mode.",
        "Ping now runs loopback-to-loopback and accepts both busybox and iputils output "
        "(the old string matched busybox only).",
    ]
    return t


# ---------------------------------------------------------------------------
# OSPF adjacency troubleshooting (addressing plan corrected -> new runs needed)
# ---------------------------------------------------------------------------
TS_PLAN = {
    "R1": {"eth1": "10.0.12.1/30", "eth2": "10.0.14.1/30", "lo": "10.0.0.1/32"},
    "R2": {"eth1": "10.0.12.2/30", "eth2": "10.0.23.1/30", "lo": "10.0.0.2/32"},
    "R3": {"eth1": "10.0.23.2/30", "eth2": "10.0.34.1/30", "lo": "10.0.0.3/32"},
    "R4": {"eth1": "10.0.34.2/30", "eth2": "10.0.14.2/30", "lo": "10.0.0.4/32"},
}
TS_AREAS = {  # interface network -> area (R3's eth1 network is the injected fault)
    "R1": [("10.0.0.1/32", 0), ("10.0.12.0/30", 0), ("10.0.14.0/30", 0)],
    "R2": [("10.0.0.2/32", 0), ("10.0.12.0/30", 0), ("10.0.23.0/30", 0)],
    "R3": [("10.0.0.3/32", 0), ("10.0.23.0/30", 1), ("10.0.34.0/30", 0)],
    "R4": [("10.0.0.4/32", 0), ("10.0.34.0/30", 0), ("10.0.14.0/30", 0)],
}


def _plan_text(plan):
    return "\n".join(
        f"- {n}: " + ", ".join(f"{i}={a}" for i, a in ifs.items()) for n, ifs in plan.items()
    )


def _preconf(plan, areas):
    steps = []
    for node, ifs in plan.items():
        lines = ["conf t"]
        for ifname in ("lo", "eth1", "eth2"):
            if ifname in ifs:
                lines += [f" interface {ifname}", f"  ip address {ifs[ifname]}", " exit"]
        rid = ifs["lo"].split("/")[0]
        lines += [" router ospf", f"  ospf router-id {rid}"]
        lines += [f"  network {net} area {area}" for net, area in areas[node]]
        steps.append({"node": node, "command": "vtysh -c '" + "\n".join(lines) + "'"})
    return steps


def ospf_ts(t):
    t["description"] = (
        "OSPF adjacency troubleshooting scenario. A 4-router OSPF ring (R1-R2-R3-R4-R1) should run "
        "entirely in Area 0, but one router is misconfigured so that one adjacency never forms. "
        "Identify the root cause and restore full OSPF operation. Traffic currently survives only "
        "because the ring routes around the broken link.\n\nIP Addressing Plan:\n" + _plan_text(TS_PLAN)
    )
    t["preconfiguration"] = _preconf(TS_PLAN, TS_AREAS)
    t["intent"]["properties"] = [
        rx("fault_corrected", "ospf_configuration",
           "R3's link to R2 (eth1) is back in the backbone area (Area 0)",
           "R3", "vtysh -c 'show ip ospf interface eth1'", r"Area 0\.0\.0\.0\b"),
        rx("r2_r3_adjacency_full", "ospf_configuration",
           "The OSPF adjacency between R2 and R3 (router-id 10.0.0.3) is Full",
           "R2", "vtysh -c 'show ip ospf neighbor'", nbr_full("10.0.0.3")),
        rx("r2_uses_restored_link", "route_exists",
           "R2 now reaches R3's loopback over the repaired direct link",
           "R2", "vtysh -c 'show ip route 10.0.0.3/32'",
           r'Known via "ospf".*^\s*\*\s*10\.0\.23\.2, via eth2'),
        rx("topology_reconverged", "route_exists",
           "A router not adjacent to the fault (R1) has re-converged: it load-shares to R3 via R2 and R4",
           "R1", "vtysh -c 'show ip route 10.0.0.3/32'",
           r"\A(?=.*10\.0\.12\.2, via eth1)(?=.*10\.0\.14\.2, via eth2)"),
    ]
    t["fault_verification"] = [
        rx("verify_ospf_running", "ospf_configuration", "R2 has a Full adjacency with R1 (OSPF is up)",
           "R2", "vtysh -c 'show ip ospf neighbor'", nbr_full("10.0.0.1")),
        rx("verify_fault_injected", "ospf_configuration", "R3 eth1 is in Area 1 (fault present)",
           "R3", "vtysh -c 'show ip ospf interface eth1'", r"Area 0\.0\.0\.1\b"),
        rx("verify_adjacency_missing", "ospf_configuration", "R2-R3 adjacency is not Full",
           "R2", "vtysh -c 'show ip ospf neighbor'", nbr_full("10.0.0.3"), must_match=False),
        rx("verify_ring_otherwise_up", "reachability", "R1 reaches R4's loopback (rest of ring works)",
           "R1", ping("R1", "10.0.0.1", "10.0.0.4"), PING_OK),
    ]
    t["convergence"] = {"timeout_seconds": 60, "check_interval_seconds": 3}
    t["optimal_solution"]["description"] = (
        "Inspect neighbors and OSPF interfaces, find R3 eth1 in Area 1, move 10.0.23.0/30 on R3 "
        "into Area 0, verify the R2-R3 adjacency and the resulting routes."
    )
    CHANGES[t["task_id"]] = [
        "Addressing plan fixed. The old plan put 10.0.23.3/30 (a broadcast address) on R3 and "
        "10.0.14.4/30 / 10.0.34.4/30 (other subnets) on R4, so R4 could never form an adjacency.",
        "Description corrected: the fault is an area-ID mismatch (the paper said MTU/timers).",
        "All four properties replaced. Old initial_problem_identified searched for the text 'R3' in "
        "a table that only lists router IDs (always true); root_cause_diagnosed matched the word "
        "'area' (true while the fault was present); adjacency_restored matched R2's Full adjacency "
        "with R1; full_topology_convergence depended on the addressing bug, not on the fault.",
        "New properties form a real dependency chain: fix -> adjacency -> R2 route -> remote re-convergence. "
        "All are false in the faulted baseline.",
        "fault_verification now also checks that OSPF is running and the fault is present, so a "
        "failed preconfiguration can no longer pass silently.",
        "Convergence budget raised 45s -> 60s so the ring converges before fault verification ends.",
    ]
    return t


# ---------------------------------------------------------------------------
# Multi-area OSPF (addressing plan corrected; summaries made explicit)
# ---------------------------------------------------------------------------
MA_PLAN = {
    "R1": {"eth1": "10.0.12.1/30", "eth2": "10.0.13.1/30", "lo": "10.0.0.1/32"},
    "R2": {"eth1": "10.0.12.2/30", "eth2": "10.1.24.1/30", "lo": "10.0.0.2/32"},
    "R3": {"eth1": "10.0.13.2/30", "eth2": "10.2.35.1/30", "lo": "10.0.0.3/32"},
    "R4": {"eth1": "10.1.24.2/30", "lo": "10.1.255.4/32"},
    "R5": {"eth1": "10.2.35.2/30", "lo": "10.2.255.5/32"},
}


def ospf_ma(t):
    t["description"] = (
        "Multi-area OSPF deployment across 5 routers. Area 0 (backbone) contains R1 and the "
        "backbone links of R2 and R3. R2 is the ABR for Area 1 (R2-R4 link and R4); R3 is the ABR "
        "for Area 2 (R3-R5 link and R5). Use router-ids 10.0.0.N for RN. Configure OSPF with the "
        "correct area assignments, summarize Area 1 as 10.1.0.0/16 at R2 and Area 2 as "
        "10.2.0.0/16 at R3, and verify end-to-end reachability between the two non-backbone "
        "areas.\n\nIP Addressing Plan:\n" + _plan_text(MA_PLAN)
    )
    route_cmd = "vtysh -c 'show ip ospf route'"
    t["intent"]["properties"] = [
        rx("backbone_adjacencies_full", "ospf_configuration",
           "R1 has Full adjacencies with both ABRs (R2 and R3) in Area 0",
           "R1", "vtysh -c 'show ip ospf neighbor'",
           rf"\A(?=.*{nbr_full('10.0.0.2')})(?=.*{nbr_full('10.0.0.3')})"),
        rx("area1_adjacency_full", "ospf_configuration", "R4 has a Full adjacency with its ABR R2",
           "R4", "vtysh -c 'show ip ospf neighbor'", nbr_full("10.0.0.2")),
        rx("area2_adjacency_full", "ospf_configuration", "R5 has a Full adjacency with its ABR R3",
           "R5", "vtysh -c 'show ip ospf neighbor'", nbr_full("10.0.0.3")),
        rx("interarea_routes_in_backbone", "ospf_configuration",
           "R1 holds inter-area routes for both Area 1 and Area 2 prefixes",
           "R1", route_cmd, r"\A(?=.*^N IA\s+10\.1\.)(?=.*^N IA\s+10\.2\.)"),
        rx("area1_to_area2_reachability", "reachability",
           "R4's loopback (Area 1) reaches R5's loopback (Area 2)",
           "R4", ping("R4", "10.1.255.4", "10.2.255.5"), PING_OK),
        rx("area1_summarized", "ospf_configuration",
           "R2 advertises Area 1 into the backbone as the single summary 10.1.0.0/16",
           "R1", route_cmd, r"\A(?=.*^N IA\s+10\.1\.0\.0/16)(?!.*^N IA\s+10\.1\.24\.0/30)"),
        rx("area2_summarized", "ospf_configuration",
           "R3 advertises Area 2 into the backbone as the single summary 10.2.0.0/16",
           "R1", route_cmd, r"\A(?=.*^N IA\s+10\.2\.0\.0/16)(?!.*^N IA\s+10\.2\.35\.0/30)"),
    ]
    CHANGES[t["task_id"]] = [
        "Addressing plan fixed. The old plan put 10.0.13.3/30 (broadcast) on R3 and "
        "10.1.24.4/30 and 10.2.35.5/30 in different subnets from their neighbors, cutting off R4 and R5.",
        "R1 was labelled an ABR but has only Area 0 links; description corrected.",
        "Summaries made explicit (10.1.0.0/16, 10.2.0.0/16) and area-local loopbacks moved into those "
        "ranges so summarization is observable.",
        "area1_routes_visible and route_summarization searched 'show ip route' for 'O IA', which FRR "
        "never prints (0/14 runs, even one with working inter-area routing). Replaced with checks on "
        "'show ip ospf route' ('N IA'), which is where FRR marks inter-area routes.",
        "route_summarization now checks that the summary exists and the component /30 is suppressed.",
        "Added per-area adjacency checks so partial progress in each area is visible.",
    ]
    return t


# ---------------------------------------------------------------------------
# BGP dual-homing (addressing valid; description unchanged so logged runs replay)
# ---------------------------------------------------------------------------
def bgp(t):
    est = r"remote AS {asn}\b.*BGP state = Established"
    design = (
        "\n\nEDGE1, EDGE2, and CORE are autonomous system 65100. EDGE1 has an established "
        "session with ISP1 (AS 65001), and EDGE2 has an established session with ISP2 (AS 65002). "
        "The enterprise advertises only prefixes inside 10.0.0.0/8. ISP1 learns at least one such "
        "prefix from EDGE1 and learns nothing outside 10.0.0.0/8 from EDGE1. Routes that EDGE1 "
        "learns from ISP1 have local preference above 100. ISP2 receives an enterprise prefix "
        "inside 10.0.0.0/8 from EDGE2 whose AS path repeats an AS. The EDGE1 session with ISP1 "
        "has a hold time below 60 seconds."
    )
    if "65100" not in t["description"]:
        t["description"] = t["description"].rstrip() + design
    # route line learned from a peer: '*> <net> <nexthop> ... <AS path> <origin>'
    learned_from = r"^\*\S*\s+{net}\s+{nh}\s[^\n]*\s\d+(?: \d+)* [ie?]$"
    t["intent"]["properties"] = [
        rx("ebgp_isp1_established", "bgp_configuration",
           "eBGP session from EDGE1 to ISP1 (AS 65001) is Established",
           "EDGE1", "vtysh -c 'show ip bgp neighbors 203.0.113.1'", est.format(asn=65001)),
        rx("ebgp_isp2_established", "bgp_configuration",
           "eBGP session from EDGE2 to ISP2 (AS 65002) is Established",
           "EDGE2", "vtysh -c 'show ip bgp neighbors 198.51.100.1'", est.format(asn=65002)),
        rx("outbound_filtering", "bgp_configuration",
           "ISP1 learns at least one enterprise (10/8) prefix from EDGE1 and nothing else from EDGE1",
           "ISP1", "vtysh -c 'show ip bgp'",
           r"\A(?=.*" + learned_from.format(net=r"10\.\d+\.\d+\.\d+/\d+", nh=r"203\.0\.113\.2") + ")"
           r"(?!.*" + learned_from.format(net=r"(?!10\.)\d+\.\d+\.\d+\.\d+/\d+", nh=r"203\.0\.113\.2") + ")"),
        rx("primary_path_preference", "bgp_configuration",
           "EDGE1 assigns local-preference above the default (100) to routes learned from ISP1",
           "EDGE1", "vtysh -c 'show ip bgp json'",
           r'"locPrf":\s*(?:10[1-9]|1[1-9]\d|[2-9]\d\d|\d{4,}),[^{}]*"path":\s*"65001\b'),
        rx("as_path_prepending", "bgp_configuration",
           "ISP2 receives an enterprise prefix from EDGE2 with a prepended (repeated) AS path",
           "ISP2", "vtysh -c 'show ip bgp'",
           r"^\*\S*\s+10\.\d+\.\d+\.\d+/\d+\s+198\.51\.100\.2\s[^\n]*\b(\d+)(?: \1\b)+(?: \d+)* [ie?]$"),
        rx("fast_failover_timers", "bgp_configuration",
           "The negotiated hold time on EDGE1's ISP1 session is below 60 seconds",
           "EDGE1", "vtysh -c 'show ip bgp neighbors 203.0.113.1'",
           r"^\s*Hold time is (?:[1-9]|[1-5]\d)\b"),
    ]
    CHANGES[t["task_id"]] = [
        "Session checks matched '65001'/'65002' anywhere in the summary (true once a neighbor was "
        "configured, even if Idle). Now require 'BGP state = Established' for that neighbor.",
        "route_filtering_outbound only required ISP1 to hold some 10.0.0.0 route; a logged run made "
        "ISP1 originate it locally. Now the prefix must be learned from EDGE1 (next hop 203.0.113.2, "
        "non-empty AS path) and EDGE1 must advertise nothing outside 10/8.",
        "primary_path_preference matched the word 'best' in EDGE1's default route (a run originated "
        "the default on EDGE1 itself). Now requires local-preference > 100 on routes whose AS path "
        "starts with 65001.",
        "as_path_prepending matched any line containing 'route-map' (a run created a route-map named "
        "'route-map'). Now requires ISP2 to receive an enterprise prefix with a repeated AS in its path.",
        "Hold-time check anchored to the negotiated value and accepts any value below 60s, as the "
        "property text states ('Hold time is 300' no longer matches).",
        "Task text now pins enterprise AS 65100, advertisements inside 10.0.0.0/8, and "
        "local-preference above 100 on EDGE1 for routes learned from ISP1. Topology is unchanged, "
        "so earlier command logs remain replayable.",
    ]
    return t


BUILDERS = {
    "ccna_rip_routing_basic": rip,
    "troubleshoot_ospf_adjacency_issue": ospf_ts,
    "ccnp_multiarea_ospf_intermediate": ospf_ma,
    "ccie_bgp_dual_homing_expert": bgp,
}

REPLAYABLE = {"ccna_rip_routing_basic", "ccie_bgp_dual_homing_expert"}


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    md = ["# v2 task changes\n",
          "Generated by `experiments/replay_v2/build_v2_tasks.py`. Originals in `tasks/multi_turn/` are untouched.\n"]
    for task_id, build in BUILDERS.items():
        t = build(copy.deepcopy(json.loads((SRC / f"{task_id}.json").read_text())))
        t["version"] = "v2"
        (DST / f"{task_id}.json").write_text(json.dumps(t, indent=2) + "\n")
        replay = "yes (description and topology unchanged)" if task_id in REPLAYABLE else \
            "no: topology/addressing changed, needs new agent runs"
        md.append(f"\n## {task_id}\n\nLogged runs replayable: **{replay}**\n")
        md += [f"- {c}" for c in CHANGES[task_id]]
    (DST / "CHANGES.md").write_text("\n".join(md) + "\n")
    print("wrote", ", ".join(sorted(BUILDERS)))


if __name__ == "__main__":
    main()
