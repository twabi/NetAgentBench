"""Small helpers to drive a task topology in the netns lab and evaluate its properties
with the harness's own PropertyEvaluator (no harness code is modified)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from benchmark.evaluator.property import PropertyEvaluator
from benchmark.executor.command import CommandExecutor
from benchmark.models.task import TaskDefinition

INFRA = "netns"  # set to "containerlab" to drive the real substrate


def make_provider():
    if INFRA == "containerlab":
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        return ContainerlabProvider()
    from netns_lab import NetnsProvider, patch_command_executor
    provider = NetnsProvider()
    patch_command_executor(provider)
    return provider

Step = Tuple[str, str]  # (node, shell command)


def load_task(path: str | Path) -> TaskDefinition:
    return TaskDefinition(**json.loads(Path(path).read_text()))


class Lab:
    def __init__(self, task: TaskDefinition):
        self.task = task
        self.provider = make_provider()
        self.topo = self.provider.provision(task.topology)
        start = time.time()
        while not self.provider.is_ready(self.topo):
            if time.time() - start > 120:
                self.close()
                raise RuntimeError("topology not ready after 120 s")
            time.sleep(2)
        self.executor = CommandExecutor()  # docker exec, or netns when patched
        self.evaluator = PropertyEvaluator()
        self.wait_for_shell()

    def wait_for_shell(self, timeout: float = 90.0) -> None:
        """Block until vtysh answers on every node. Container 'running' precedes zebra."""
        nodes = [node.name for node in self.task.topology.nodes]
        start = time.time()
        while time.time() - start < timeout:
            ready = True
            for node in nodes:
                try:
                    out, code = self.run(node, "vtysh -c 'show ip route'")
                except Exception:
                    ready = False
                    break
                if code != 0 or "not running" in (out or "").lower():
                    ready = False
                    break
            if ready:
                time.sleep(3)
                return
            time.sleep(2)
        raise RuntimeError("vtysh not ready after 90 s")

    def ns(self, node: str) -> str:
        return self.provider.get_node_container_name(self.topo, node)

    def run(self, node: str, command: str) -> Tuple[str, int]:
        out, _, code = self.executor.exec_on_node(self.ns(node), command)
        return out, code

    def apply(self, steps: Iterable[Step]) -> List[Tuple[str, str, int, str]]:
        log = []
        for node, cmd in steps:
            out, code = self.run(node, cmd)
            if code != 0 and "not running" in (out or "").lower():
                self.wait_for_shell()
                out, code = self.run(node, cmd)
            log.append((node, cmd, code, out))
        return log

    def preconfigure(self) -> List[Tuple[str, str, int, str]]:
        steps = list(self.task.preconfiguration or [])
        log = self.apply((step.node, step.command) for step in steps)
        if any(code != 0 and "not running" in (out or "").lower() for _, _, code, out in log):
            self.wait_for_shell()
            log = self.apply((step.node, step.command) for step in steps)
        return log

    def evaluate(self, properties=None) -> dict:
        props = properties if properties is not None else self.task.intent.properties
        res = self.evaluator.evaluate_all_properties(self.provider, self.topo, props)
        return {r.property_id: r.satisfied for r in res}

    def evaluate_detail(self, properties=None):
        props = properties if properties is not None else self.task.intent.properties
        return self.evaluator.evaluate_all_properties(self.provider, self.topo, props)

    def wait_for(self, predicate, timeout: float, interval: float = 3.0) -> float:
        start = time.time()
        while time.time() - start < timeout:
            if predicate():
                return time.time() - start
            time.sleep(interval)
        return -1.0

    def close(self) -> None:
        self.provider.teardown(self.topo)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
