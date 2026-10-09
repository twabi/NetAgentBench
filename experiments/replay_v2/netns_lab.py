"""Linux network-namespace substitute for Containerlab (for replay without Docker Hub).

Each topology node becomes a network namespace running FRR daemons in their own
pathspace (``-N <ns>``). Links are veth pairs renamed to the task's interface
names (eth1, eth2, ...) with MTU 9500, matching Containerlab's default.

Commands are executed exactly as the harness does in a container
(``/bin/sh -c <command>``), inside the node's namespace. A per-node ``vtysh``
shim on PATH adds ``-N <ns>`` so task commands such as ``vtysh -c '...'`` run
unchanged.

Differences from the Containerlab substrate (document these when reporting):
  * FRR version is whatever the host package provides (Ubuntu 24.04: 8.4.x),
    not the ``frrouting/frr:latest`` image (10.x at the time of the study).
  * No management interface (eth0) and no UTS namespace (hostname is shared).
  * `ping` is busybox (as in the Alpine-based FRR image) when busybox is installed.
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.models.task import TopologySpecification

DAEMONS = ["zebra", "staticd", "ripd", "ospfd", "bgpd"]
FRR_BIN = Path("/usr/lib/frr")
RUN_ROOT = Path("/var/run/frr")
ETC_ROOT = Path("/etc/frr")
SHIM_ROOT = Path("/opt/nsbin")
VETH_MTU = 9500


def _sh(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


class NetnsProvider(InfrastructureProvider):
    """InfrastructureProvider backed by network namespaces + host FRR."""

    def __init__(self) -> None:
        self._topos: Dict[str, Dict[str, str]] = {}  # topo_id -> {node: ns}

    # ---- InfrastructureProvider -------------------------------------------------
    def provision(self, topology: TopologySpecification) -> str:
        topo_id = uuid.uuid4().hex[:6]
        nodes = {n.name: f"t{topo_id}{n.name}"[:15] for n in topology.nodes}
        self._topos[topo_id] = nodes
        try:
            for node, ns in nodes.items():
                self._make_node(ns)
            for i, link in enumerate(topology.links):
                (a_node, a_if), (b_node, b_if) = (e.split(":") for e in link.endpoints)
                self._make_link(nodes[a_node], a_if, nodes[b_node], b_if, f"{topo_id}{i}")
            for ns in nodes.values():
                self._start_frr(ns)
        except Exception:
            self.teardown(topo_id)
            raise
        return topo_id

    def is_ready(self, topology_id: str) -> bool:
        for ns in self._topos.get(topology_id, {}).values():
            out = self.exec(ns, "vtysh -c 'show version'")
            if out[2] != 0:
                return False
        return True

    def teardown(self, topology_id: str) -> bool:
        for ns in self._topos.pop(topology_id, {}).values():
            run_dir = RUN_ROOT / ns
            for pid_file in run_dir.glob("*.pid"):
                try:
                    os.kill(int(pid_file.read_text().strip()), signal.SIGTERM)
                except (ValueError, ProcessLookupError, PermissionError):
                    pass
            time.sleep(0.3)
            _sh(["ip", "netns", "del", ns], check=False)
            for d in (run_dir, ETC_ROOT / ns, SHIM_ROOT / ns):
                shutil.rmtree(d, ignore_errors=True)
        return True

    def get_node_container_name(self, topology_id: str, node_name: str) -> str:
        return self._topos[topology_id][node_name]

    # ---- execution ----------------------------------------------------------
    @staticmethod
    def exec(ns: str, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Mirror of CommandExecutor.exec_on_node: stdout+stderr merged."""
        env_path = f"{SHIM_ROOT / ns}:/usr/sbin:/usr/bin:/sbin:/bin"
        try:
            proc = subprocess.run(
                ["ip", "netns", "exec", ns, "env", f"PATH={env_path}", "/bin/sh", "-c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Command '{command}' timed out after {timeout} seconds on {ns}") from exc
        return proc.stdout, "", proc.returncode

    # ---- helpers ------------------------------------------------------------
    def _make_node(self, ns: str) -> None:
        _sh(["ip", "netns", "add", ns])
        _sh(["ip", "-n", ns, "link", "set", "lo", "up"])
        for key, val in (
            ("net.ipv4.ip_forward", "1"),
            ("net.ipv4.conf.all.rp_filter", "0"),
            ("net.ipv4.conf.default.rp_filter", "0"),
        ):
            _sh(["ip", "netns", "exec", ns, "sysctl", "-qw", f"{key}={val}"])
        etc = ETC_ROOT / ns
        etc.mkdir(parents=True, exist_ok=True)
        (etc / "vtysh.conf").write_text("service integrated-vtysh-config\n")
        (etc / "frr.conf").write_text("")
        run = RUN_ROOT / ns
        run.mkdir(parents=True, exist_ok=True)
        shutil.chown(run, "frr", "frr")
        shim = SHIM_ROOT / ns
        shim.mkdir(parents=True, exist_ok=True)
        (shim / "vtysh").write_text(f'#!/bin/sh\nexec /usr/bin/vtysh -N {shlex.quote(ns)} "$@"\n')
        (shim / "vtysh").chmod(0o755)
        # The frrouting/frr image is Alpine-based: `ping` is busybox, whose summary line
        # ("3 packets received") differs from iputils ("3 received"). Match the container.
        if shutil.which("busybox"):
            (shim / "ping").write_text('#!/bin/sh\nexec busybox ping "$@"\n')
            (shim / "ping").chmod(0o755)

    @staticmethod
    def _make_link(ns_a: str, if_a: str, ns_b: str, if_b: str, tag: str) -> None:
        tmp_a, tmp_b = f"va{tag}"[:15], f"vb{tag}"[:15]
        _sh(["ip", "link", "add", tmp_a, "type", "veth", "peer", "name", tmp_b])
        for tmp, ns, name in ((tmp_a, ns_a, if_a), (tmp_b, ns_b, if_b)):
            _sh(["ip", "link", "set", tmp, "netns", ns])
            _sh(["ip", "-n", ns, "link", "set", tmp, "name", name])
            _sh(["ip", "-n", ns, "link", "set", name, "mtu", str(VETH_MTU)])
            _sh(["ip", "-n", ns, "link", "set", name, "up"])

    @staticmethod
    def _start_frr(ns: str) -> None:
        run = RUN_ROOT / ns
        for daemon in DAEMONS:
            args = [
                "ip", "netns", "exec", ns, str(FRR_BIN / daemon),
                "-d", "-N", ns, "-F", "traditional",
                "-i", str(run / f"{daemon}.pid"),
                "--log", f"file:{run / (daemon + '.log')}",
            ]
            _sh(args)
            if daemon == "zebra":
                time.sleep(0.5)
        time.sleep(0.5)


def patch_command_executor(provider: NetnsProvider) -> None:
    """Route the harness's CommandExecutor.exec_on_node through the netns lab."""
    from benchmark.executor.command import CommandExecutor

    def exec_on_node(self, container_name: str, command: str, timeout: int = 30):
        return provider.exec(container_name, command, timeout=timeout)

    CommandExecutor.exec_on_node = exec_on_node  # type: ignore[assignment]
