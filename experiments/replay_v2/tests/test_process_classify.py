"""Content-based command classification used by analyze_process.py.

Cases are taken from the v2 OpenRouter logs, where the agent-supplied read/config
label disagreed with what the command did.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_process import classify, config_lines, disruptive_kinds  # noqa: E402


@pytest.mark.parametrize("cmd,expected", [
    # labelled config by GLM after a tool-argument error, but read-only
    ("vtysh -c 'show ip ospf neighbor'", "read"),
    ("vtysh -c 'show run' ; vtysh -c 'show ip ospf interface eth2'", "read"),
    ("ping -c 3 -W 2 10.0.23.1", "read"),
    # labelled read by Qwen, but they change live state
    ("vtysh -c 'clear ip bgp 198.51.100.1'", "write"),
    ("vtysh -c 'configure terminal' -c 'route-map TEST permit 10' -c 'set as-path prepend 65100'", "write"),
    ('vtysh -c "conf" -c "router ospf" -c "network 0.0.0.0 0.0.0.0 area 0" 2>&1', "write"),
    ("vtysh -c 'conf t' -c 'interface eth1' -c 'no ip rip authentication mode' -c 'end'", "write"),
    ("ip addr add 10.0.12.1/30 dev eth1", "write"),
    # entering config mode only to ask for help or turn on logging changes no routing state
    ("vtysh -c 'configure terminal' -c 'router bgp 65100' -c 'neighbor 198.51.100.1' -c '?'", "read"),
    ("vtysh -c 'conf t' -c 'debug rip events' -c 'end'", "read"),
    ("vtysh -c 'write memory' >/dev/null 2>&1; echo saved", "persist"),
])
def test_classify(cmd, expected):
    assert classify(cmd) == expected


def test_route_map_context_creates_object():
    # entering 'route-map X permit 10' creates the route-map even with only a help query after it
    assert classify("vtysh -c 'configure terminal' -c 'route-map TEST permit 10' -c 'set as-path' -c '?'") == "write"


def test_config_lines_drop_navigation():
    cmd = ('vtysh -c "configure terminal" -c "router bgp 65000" -c "address-family ipv4 unicast" '
           '-c "neighbor 203.0.113.1 route-map FILTER-OUT out" -c "exit-address-family" -c "exit"')
    assert config_lines(cmd) == ["neighbor 203.0.113.1 route-map FILTER-OUT out"]


@pytest.mark.parametrize("cmd,kinds", [
    ("vtysh -c 'clear ip bgp *'", ["hard session/process reset"]),
    ("vtysh -c 'clear bgp 203.0.113.1 soft out'", []),
    ("vtysh -c 'conf t' -c 'interface eth1' -c 'ip ospf network point-to-point'", ["OSPF network-type change"]),
    # the correct OSPF-TS repair is reconfiguration, not disruption
    ("vtysh -c 'configure terminal' -c 'router ospf' -c 'no network 10.0.23.0/30 area 1' "
     "-c 'network 10.0.23.0/30 area 0'", []),
    ("vtysh -c 'conf t' -c 'no router rip'", ["removal of protocol process or peer"]),
])
def test_disruptive_kinds(cmd, kinds):
    assert disruptive_kinds(cmd) == kinds
