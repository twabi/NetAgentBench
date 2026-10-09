"""
Task presentation module for formatting tasks in human-readable formats.

Provides multiple presentation formats:
- Plain text: Human-readable text format
- Markdown: Formatted markdown with sections
- JSON: Pretty-printed JSON
"""
import io
import json
from typing import Dict, List, Optional
from benchmark.models.task import TaskDefinition, Property, Node, Link


class TaskPresenter:
    """
    Formats benchmark tasks for human presentation.
    
    Supports multiple output formats:
    - Text: Plain text, human-readable
    - Markdown: Formatted markdown with headers and code blocks
    - JSON: Pretty-printed JSON representation
    """

    def present_task_text(self, task: TaskDefinition) -> str:
        """
        Present task in plain text format.
        
        Args:
            task: TaskDefinition to present
        
        Returns:
            Human-readable text representation
        """
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append(f"TASK: {task.task_id}")
        lines.append("=" * 70)
        lines.append("")
        
        # Description
        lines.append("Description:")
        lines.append(f"  {task.description}")
        lines.append("")
        
        # Platform
        platform_str = task.platform.value if hasattr(task.platform, "value") else str(task.platform)
        lines.append(f"Platform: {platform_str}")
        lines.append("")
        
        # Topology
        lines.append("Network Topology:")
        lines.append("-" * 40)
        
        # Nodes
        lines.append(f"Nodes ({len(task.topology.nodes)}):")
        for node in task.topology.nodes:
            node_type = node.type.value if hasattr(node.type, "value") else str(node.type)
            node_platform = node.platform.value if hasattr(node.platform, "value") else str(node.platform)
            lines.append(
                f"  - {node.name}: {node_type} ({node_platform})"
            )
        lines.append("")
        
        # Links
        lines.append(f"Links ({len(task.topology.links)}):")
        for i, link in enumerate(task.topology.links, 1):
            endpoints = " <--> ".join(link.endpoints)
            lines.append(f"  {i}. {endpoints}")
        lines.append("")

        # Topology diagram
        lines.append("Topology Diagram:")
        lines.append(self._generate_simple_topology_diagram(task))
        lines.append("")

        # Intent / Properties
        lines.append("Success Criteria:")
        lines.append("-" * 40)
        lines.append("The network must satisfy the following properties:")
        lines.append("")
        for i, prop in enumerate(task.intent.properties, 1):
            lines.append(f"{i}. {prop.description}")
            lines.append(f"   Type: {prop.type}")
            lines.append(f"   Verification: {prop.evaluation.method}")
            lines.append(f"   Command: {prop.evaluation.command}")
            lines.append("")
        
        # Convergence info
        if task.convergence:
            lines.append(f"Convergence timeout: {task.convergence.timeout_seconds}s")
            lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)

    def present_task_markdown(self, task: TaskDefinition) -> str:
        """
        Present task in markdown format.
        
        Args:
            task: TaskDefinition to present
        
        Returns:
            Markdown-formatted representation
        """
        lines = []
        
        # Header
        lines.append(f"# Task: {task.task_id}")
        lines.append("")
        lines.append(f"**Description:** {task.description}")
        lines.append("")
        platform_str = task.platform.value if hasattr(task.platform, "value") else str(task.platform)
        lines.append(f"**Platform:** `{platform_str}`")
        lines.append("")
        
        # Topology
        lines.append("## Network Topology")
        lines.append("")
        
        # Nodes
        lines.append(f"### Nodes ({len(task.topology.nodes)})")
        lines.append("")
        for node in task.topology.nodes:
            node_type = node.type.value if hasattr(node.type, "value") else str(node.type)
            node_platform = node.platform.value if hasattr(node.platform, "value") else str(node.platform)
            lines.append(
                f"- **{node.name}**: {node_type} (`{node_platform}`)"
            )
        lines.append("")
        
        # Links
        lines.append(f"### Links ({len(task.topology.links)})")
        lines.append("")
        for link in task.topology.links:
            endpoints = " ↔ ".join(link.endpoints)
            lines.append(f"- {endpoints}")
        lines.append("")
        
        # Topology diagram (simple ASCII)
        lines.append("### Topology Diagram")
        lines.append("")
        lines.append("```")
        lines.append(self._generate_simple_topology_diagram(task))
        lines.append("```")
        lines.append("")
        
        # Properties
        lines.append("## Success Criteria")
        lines.append("")
        lines.append("The network configuration must satisfy:")
        lines.append("")
        
        for i, prop in enumerate(task.intent.properties, 1):
            lines.append(f"### {i}. {prop.description}")
            lines.append("")
            lines.append(f"- **Type:** `{prop.type}`")
            lines.append(f"- **Verification method:** `{prop.evaluation.method}`")
            lines.append(f"- **Test command:**")
            lines.append(f"  ```bash")
            lines.append(f"  {prop.evaluation.command}")
            lines.append(f"  ```")
            lines.append("")
        
        # Configuration requirements
        lines.append("## Configuration Requirements")
        lines.append("")
        if task.convergence:
            lines.append(
                f"- Convergence timeout: {task.convergence.timeout_seconds} seconds"
            )
        if task.optimal_solution:
            lines.append(
                f"- Optimal command count: {task.optimal_solution.command_count}"
            )
        lines.append("")
        
        return "\n".join(lines)

    def present_task_json(self, task: TaskDefinition) -> str:
        """
        Present task in pretty-printed JSON format.
        
        Args:
            task: TaskDefinition to present
        
        Returns:
            Pretty-printed JSON string
        """
        # Use pydantic's model_dump to get dict representation
        task_dict = task.model_dump(mode="json")
        
        # Pretty-print with indentation
        return json.dumps(task_dict, indent=2, ensure_ascii=False)

    def _generate_simple_topology_diagram(self, task: TaskDefinition) -> str:
        """
        Generate a shape-aware topology diagram.

        Detects common network shapes (single node, pair, linear chain,
        ring, tree/star) and renders each accordingly. Falls back to a
        flat edge list for anything else (e.g. mesh topologies).

        Args:
            task: TaskDefinition with topology

        Returns:
            Text diagram of the topology
        """
        node_names = [node.name for node in task.topology.nodes]
        adjacency = self._build_adjacency(task.topology.links)
        shape = self._classify_topology(node_names, adjacency)

        if shape == "single":
            return node_names[0]
        if shape == "pair":
            return f"{node_names[0]} -------- {node_names[1]}"
        if shape == "linear":
            order = self._trace_linear_order(node_names, adjacency)
            return " ----- ".join(order)
        if shape == "ring":
            order = self._trace_ring_order(node_names, adjacency)
            loop = " -- ".join(order)
            return f"{loop} -- (back to {order[0]})"
        if shape == "tree":
            return self._render_tree(node_names, adjacency)

        # Generic fallback: flat edge list
        lines = []
        for link in task.topology.links:
            ep1, ep2 = link.endpoints[0], link.endpoints[1]
            node1 = ep1.split(":")[0]
            node2 = ep2.split(":")[0]
            lines.append(f"{node1} <----> {node2}")
        return "\n".join(lines)

    def _build_adjacency(self, links: List[Link]) -> Dict[str, List[str]]:
        """Build an ordered adjacency list from link endpoints (node:iface)."""
        adjacency: Dict[str, List[str]] = {}
        for link in links:
            n1 = link.endpoints[0].split(":")[0]
            n2 = link.endpoints[1].split(":")[0]
            adjacency.setdefault(n1, []).append(n2)
            adjacency.setdefault(n2, []).append(n1)
        return adjacency

    def _classify_topology(
        self, node_names: List[str], adjacency: Dict[str, List[str]]
    ) -> str:
        """Classify a topology's shape from node names and adjacency lists."""
        n = len(node_names)
        if n <= 1:
            return "single"
        if n == 2:
            return "pair"

        num_edges = sum(len(neighbors) for neighbors in adjacency.values()) // 2
        degrees = {name: len(adjacency.get(name, [])) for name in node_names}

        if not self._is_connected(node_names, adjacency):
            return "generic"

        if num_edges == n and all(d == 2 for d in degrees.values()):
            return "ring"

        if num_edges == n - 1:
            if all(d <= 2 for d in degrees.values()):
                return "linear"
            return "tree"

        return "generic"

    def _is_connected(
        self, node_names: List[str], adjacency: Dict[str, List[str]]
    ) -> bool:
        """Check whether all nodes are reachable from the first node."""
        if not node_names:
            return True
        visited = {node_names[0]}
        stack = [node_names[0]]
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        return len(visited) == len(node_names)

    def _trace_linear_order(
        self, node_names: List[str], adjacency: Dict[str, List[str]]
    ) -> List[str]:
        """Walk a linear chain from one endpoint (degree 1) to the other."""
        start = next(
            (name for name in node_names if len(adjacency.get(name, [])) == 1),
            node_names[0],
        )
        order = [start]
        prev: Optional[str] = None
        current = start
        while True:
            candidates = [n for n in adjacency.get(current, []) if n != prev]
            if not candidates:
                break
            next_node = candidates[0]
            order.append(next_node)
            prev, current = current, next_node
        return order

    def _trace_ring_order(
        self, node_names: List[str], adjacency: Dict[str, List[str]]
    ) -> List[str]:
        """Walk a ring's cyclic order starting from the first node."""
        start = node_names[0]
        order = [start]
        prev: Optional[str] = None
        current = start
        while True:
            candidates = [n for n in adjacency.get(current, []) if n != prev]
            next_node = candidates[0]
            if next_node == start:
                break
            order.append(next_node)
            prev, current = current, next_node
        return order

    def _render_tree(
        self, node_names: List[str], adjacency: Dict[str, List[str]]
    ) -> str:
        """Render a tree/star topology using rich's box-drawing Tree."""
        from rich.console import Console
        from rich.tree import Tree

        root = max(node_names, key=lambda name: len(adjacency.get(name, [])))

        def add_children(branch: Tree, name: str, visited: set) -> None:
            for child in adjacency.get(name, []):
                if child in visited:
                    continue
                visited.add(child)
                add_children(branch.add(child), child, visited)

        tree = Tree(root)
        add_children(tree, root, {root})

        buffer = io.StringIO()
        console = Console(file=buffer, width=80, force_terminal=False)
        console.print(tree)
        return buffer.getvalue().rstrip("\n")

