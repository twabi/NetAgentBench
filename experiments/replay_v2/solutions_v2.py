"""Reference and staged partial solutions for the v2 tasks (instrument check).

Each task has a list of cumulative stages. After a stage's steps are applied and the
network settles, the property vector must equal `expect` (property_id -> bool).
Stage 0 is always the untouched baseline and must be all-false. The last stage is
the reference solution and must be all-true.
"""

from __future__ import annotations


def vt(*lines: str) -> str:
    """vtysh command in the style agents used: vtysh -c 'conf t' -c '...' ..."""
    return "vtysh " + " ".join(f"-c '{l}'" for l in ("conf t",) + lines)


def addr(ifaces: dict[str, str]) -> str:
    parts: list[str] = []
    for ifname, cidr in ifaces.items():
        parts += [f"interface {ifname}", f"ip address {cidr}", "exit"]
    return vt(*parts)


# ---------------------------------------------------------------------------- RIP
RIP_IPS = {
    "R1": {"eth1": "10.1.1.1/30", "eth2": "10.1.2.1/30", "lo": "10.0.0.1/32"},
    "R2": {"eth1": "10.1.1.2/30", "eth2": "10.2.1.1/30", "lo": "10.0.0.2/32"},
    "R3": {"eth1": "10.1.2.2/30", "eth2": "10.3.1.1/30", "lo": "10.0.0.3/32"},
    "R4": {"eth1": "10.2.1.2/30", "eth2": "10.3.1.2/30", "lo": "10.0.0.4/32"},
}
RIP_P = ["rip_enabled", "ripv2_enforced", "rip_authentication", "r4_loopback_via_rip", "loopback_reachability"]


def _v(props, trues):
    return {p: (p in trues) for p in props}


RIP = [
    {"name": "baseline", "steps": [], "expect": _v(RIP_P, [])},
    {"name": "addresses + RIP with default version",
     "steps": [(n, addr(i)) for n, i in RIP_IPS.items()]
     + [(n, vt("router rip", "network 10.0.0.0/8")) for n in RIP_IPS],
     "expect": _v(RIP_P, ["rip_enabled", "r4_loopback_via_rip", "loopback_reachability"])},
    {"name": "explicit version 2",
     "steps": [(n, vt("router rip", "version 2")) for n in RIP_IPS],
     "expect": _v(RIP_P, ["rip_enabled", "ripv2_enforced", "r4_loopback_via_rip", "loopback_reachability"])},
    {"name": "reference: MD5 authentication on all router links",
     "steps": [(n, vt("key chain RIPKEY", "key 1", "key-string s3cret", "exit", "exit",
                      "interface eth1", "ip rip authentication mode md5",
                      "ip rip authentication key-chain RIPKEY", "exit",
                      "interface eth2", "ip rip authentication mode md5",
                      "ip rip authentication key-chain RIPKEY")) for n in RIP_IPS],
     "expect": _v(RIP_P, RIP_P)},
]

# ---------------------------------------------------------------- OSPF troubleshooting
TS_P = ["fault_corrected", "r2_r3_adjacency_full", "r2_uses_restored_link", "topology_reconverged"]
TS = [
    {"name": "faulted baseline", "steps": [], "expect": _v(TS_P, [])},
    {"name": "reference: move R3's 10.0.23.0/30 into Area 0",
     "steps": [("R3", vt("router ospf", "no network 10.0.23.0/30 area 1", "network 10.0.23.0/30 area 0"))],
     "expect": _v(TS_P, TS_P)},
]
# An alternative, design-wrong repair: put R2's side into Area 1 as well.
TS_WRONG_FIX = [
    {"name": "faulted baseline", "steps": [], "expect": _v(TS_P, [])},
    {"name": "wrong repair: move R2's side of the link into Area 1",
     "steps": [("R2", vt("router ospf", "no network 10.0.23.0/30 area 0", "network 10.0.23.0/30 area 1"))],
     "expect": _v(TS_P, ["r2_r3_adjacency_full"])},
]

# ------------------------------------------------------------------- multi-area OSPF
MA_IPS = {
    "R1": {"eth1": "10.0.12.1/30", "eth2": "10.0.13.1/30", "lo": "10.0.0.1/32"},
    "R2": {"eth1": "10.0.12.2/30", "eth2": "10.1.24.1/30", "lo": "10.0.0.2/32"},
    "R3": {"eth1": "10.0.13.2/30", "eth2": "10.2.35.1/30", "lo": "10.0.0.3/32"},
    "R4": {"eth1": "10.1.24.2/30", "lo": "10.1.255.4/32"},
    "R5": {"eth1": "10.2.35.2/30", "lo": "10.2.255.5/32"},
}
MA_P = ["backbone_adjacencies_full", "area1_adjacency_full", "area2_adjacency_full",
        "interarea_routes_in_backbone", "area1_to_area2_reachability", "area1_summarized", "area2_summarized"]
MA = [
    {"name": "baseline", "steps": [], "expect": _v(MA_P, [])},
    {"name": "addresses + backbone only",
     "steps": [(n, addr(i)) for n, i in MA_IPS.items()] + [
         ("R1", vt("router ospf", "ospf router-id 10.0.0.1", "network 10.0.0.1/32 area 0",
                   "network 10.0.12.0/30 area 0", "network 10.0.13.0/30 area 0")),
         ("R2", vt("router ospf", "ospf router-id 10.0.0.2", "network 10.0.0.2/32 area 0",
                   "network 10.0.12.0/30 area 0")),
         ("R3", vt("router ospf", "ospf router-id 10.0.0.3", "network 10.0.0.3/32 area 0",
                   "network 10.0.13.0/30 area 0")),
     ],
     "expect": _v(MA_P, ["backbone_adjacencies_full"])},
    {"name": "+ Area 1",
     "steps": [("R2", vt("router ospf", "network 10.1.24.0/30 area 1")),
               ("R4", vt("router ospf", "ospf router-id 10.0.0.4", "network 10.1.24.0/30 area 1",
                         "network 10.1.255.4/32 area 1"))],
     "expect": _v(MA_P, ["backbone_adjacencies_full", "area1_adjacency_full"])},
    {"name": "+ Area 2",
     "steps": [("R3", vt("router ospf", "network 10.2.35.0/30 area 2")),
               ("R5", vt("router ospf", "ospf router-id 10.0.0.5", "network 10.2.35.0/30 area 2",
                         "network 10.2.255.5/32 area 2"))],
     "expect": _v(MA_P, MA_P[:5])},
    {"name": "+ Area 1 summary at R2",
     "steps": [("R2", vt("router ospf", "area 1 range 10.1.0.0/16"))],
     "expect": _v(MA_P, MA_P[:6])},
    {"name": "reference: + Area 2 summary at R3",
     "steps": [("R3", vt("router ospf", "area 2 range 10.2.0.0/16"))],
     "expect": _v(MA_P, MA_P)},
]

# ---------------------------------------------------------------------- BGP dual-homing
BGP_IPS = {
    "EDGE1": {"eth1": "203.0.113.2/30", "eth2": "10.0.1.1/30", "lo": "10.0.0.1/32"},
    "EDGE2": {"eth1": "198.51.100.2/30", "eth2": "10.0.2.1/30", "lo": "10.0.0.2/32"},
    "ISP1": {"eth1": "203.0.113.1/30", "lo": "1.1.1.1/32"},
    "ISP2": {"eth1": "198.51.100.1/30", "lo": "2.2.2.2/32"},
    "CORE": {"eth1": "10.0.1.2/30", "eth2": "10.0.2.2/30", "lo": "10.0.0.100/32"},
}
BGP_P = ["ebgp_isp1_established", "ebgp_isp2_established", "outbound_filtering",
         "primary_path_preference", "as_path_prepending", "fast_failover_timers"]
ALLOW = ("route-map ALLOW permit 10", "exit")
BGP = [
    {"name": "baseline", "steps": [], "expect": _v(BGP_P, [])},
    {"name": "addresses, internal OSPF, eBGP sessions (no advertisements yet)",
     "steps": [(n, addr(i)) for n, i in BGP_IPS.items()] + [
         ("EDGE1", vt("router ospf", "network 10.0.0.1/32 area 0", "network 10.0.1.0/30 area 0")),
         ("EDGE2", vt("router ospf", "network 10.0.0.2/32 area 0", "network 10.0.2.0/30 area 0")),
         ("CORE", vt("router ospf", "network 10.0.0.100/32 area 0", "network 10.0.1.0/30 area 0",
                     "network 10.0.2.0/30 area 0")),
         ("ISP1", vt(*ALLOW, "router bgp 65001", "neighbor 203.0.113.2 remote-as 65100",
                     "address-family ipv4 unicast", "network 1.1.1.1/32",
                     "neighbor 203.0.113.2 route-map ALLOW in", "neighbor 203.0.113.2 route-map ALLOW out")),
         ("ISP2", vt(*ALLOW, "router bgp 65002", "neighbor 198.51.100.2 remote-as 65100",
                     "address-family ipv4 unicast", "network 2.2.2.2/32",
                     "neighbor 198.51.100.2 route-map ALLOW in", "neighbor 198.51.100.2 route-map ALLOW out")),
         ("EDGE1", vt(*ALLOW, "router bgp 65100", "bgp router-id 10.0.0.1",
                      "neighbor 203.0.113.1 remote-as 65001",
                      "neighbor 10.0.0.2 remote-as 65100", "neighbor 10.0.0.2 update-source lo",
                      "address-family ipv4 unicast", "neighbor 10.0.0.2 next-hop-self",
                      "neighbor 203.0.113.1 route-map ALLOW in")),
         ("EDGE2", vt(*ALLOW, "router bgp 65100", "bgp router-id 10.0.0.2",
                      "neighbor 198.51.100.1 remote-as 65002",
                      "neighbor 10.0.0.1 remote-as 65100", "neighbor 10.0.0.1 update-source lo",
                      "address-family ipv4 unicast", "neighbor 10.0.0.1 next-hop-self",
                      "neighbor 198.51.100.1 route-map ALLOW in")),
     ],
     "expect": _v(BGP_P, ["ebgp_isp1_established", "ebgp_isp2_established"])},
    {"name": "EDGE1 advertises 10/8 but also leaks its ISP link prefix (no outbound filter)",
     "steps": [("EDGE1", vt("ip route 10.0.0.0/8 Null0", "router bgp 65100", "address-family ipv4 unicast",
                            "network 10.0.0.0/8", "network 203.0.113.0/30",
                            "neighbor 203.0.113.1 route-map ALLOW out"))],
     # the leak must actually have reached ISP1, so outbound_filtering is false for the right reason
     "witness": [("ISP1", "vtysh -c 'show ip bgp'",
                  r"(?s)(?=.*10\.0\.0\.0/8\s+203\.0\.113\.2)(?=.*203\.0\.113\.0/30\s+203\.0\.113\.2)")],
     "expect": _v(BGP_P, ["ebgp_isp1_established", "ebgp_isp2_established"])},
    {"name": "outbound prefix-list filter on EDGE1",
     "steps": [("EDGE1", vt("ip prefix-list ENTERPRISE seq 5 permit 10.0.0.0/8 le 32",
                            "route-map TO-ISP permit 10", "match ip address prefix-list ENTERPRISE", "exit",
                            "router bgp 65100", "address-family ipv4 unicast",
                            "neighbor 203.0.113.1 route-map TO-ISP out"))],
     "expect": _v(BGP_P, ["ebgp_isp1_established", "ebgp_isp2_established", "outbound_filtering"])},
    {"name": "local-preference 200 on routes from ISP1",
     "steps": [("EDGE1", vt("route-map FROM-ISP1 permit 10", "set local-preference 200", "exit",
                            "router bgp 65100", "address-family ipv4 unicast",
                            "neighbor 203.0.113.1 route-map FROM-ISP1 in"))],
     "expect": _v(BGP_P, ["ebgp_isp1_established", "ebgp_isp2_established", "outbound_filtering",
                          "primary_path_preference"])},
    {"name": "EDGE2 advertises 10/8 to ISP2 with AS-path prepending",
     "steps": [("EDGE2", vt("ip route 10.0.0.0/8 Null0",
                            "ip prefix-list ENTERPRISE seq 5 permit 10.0.0.0/8 le 32",
                            "route-map TO-ISP2 permit 10", "match ip address prefix-list ENTERPRISE",
                            "set as-path prepend 65100 65100 65100", "exit",
                            "router bgp 65100", "address-family ipv4 unicast", "network 10.0.0.0/8",
                            "neighbor 198.51.100.1 route-map TO-ISP2 out"))],
     "expect": _v(BGP_P, BGP_P[:5])},
    {"name": "reference: BGP timers 10/30 on EDGE1's ISP1 session",
     "steps": [("EDGE1", vt("router bgp 65100", "neighbor 203.0.113.1 timers 10 30")),
               ("EDGE1", "vtysh -c 'clear bgp 203.0.113.1'")],
     "expect": _v(BGP_P, BGP_P)},
]

# ------------------------------------------------------ BGP route-filtering
FLT_P = ["filter_applied_outbound", "isp_receives_authorized_only"]
FLT = [
    {"name": "faulted baseline", "steps": [], "expect": _v(FLT_P, [])},
    {"name": "reference: FILTER-OUT replaces ALLOW-ALL outbound",
     "steps": [("EDGE", vt("router bgp 65000",
                           "neighbor 203.0.113.1 route-map FILTER-OUT out"))],
     "expect": _v(FLT_P, FLT_P)},
]
FLT_WRONG = [
    {"name": "faulted baseline", "steps": [], "expect": _v(FLT_P, [])},
    {"name": "wrong repair: FILTER-OUT applied inbound",
     "steps": [("EDGE", vt("router bgp 65000",
                           "neighbor 203.0.113.1 route-map FILTER-OUT in"))],
     "expect": _v(FLT_P, [])},
]

SCENARIOS = {
    "ccna_rip_routing_basic": {"reference": RIP},
    "troubleshoot_ospf_adjacency_issue": {"reference": TS, "wrong_fix": TS_WRONG_FIX},
    "ccnp_multiarea_ospf_intermediate": {"reference": MA},
    "ccie_bgp_dual_homing_expert": {"reference": BGP},
    "troubleshoot_bgp_route_filtering": {"reference": FLT, "wrong_fix": FLT_WRONG},
}
