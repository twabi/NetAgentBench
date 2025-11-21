"""
Task presentation module for formatting tasks in human-readable formats.

Provides multiple presentation formats:
- Plain text: Human-readable text format
- Markdown: Formatted markdown with sections
- JSON: Pretty-printed JSON
"""
import json
from typing import List
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
        Generate a simple ASCII topology diagram.
        
        Args:
            task: TaskDefinition with topology
        
        Returns:
            Simple ASCII diagram
        """
        # For simple cases, just list the nodes and links
        # More sophisticated diagrams could be added later
        
        nodes = [node.name for node in task.topology.nodes]
        
        if len(nodes) == 2:
            # Simple two-node case
            return f"{nodes[0]} -------- {nodes[1]}"
        elif len(nodes) == 3 and len(task.topology.links) == 2:
            # Linear three-node case
            return f"{nodes[0]} ----- {nodes[1]} ----- {nodes[2]}"
        else:
            # Generic case: just list connections
            lines = []
            for link in task.topology.links:
                ep1, ep2 = link.endpoints[0], link.endpoints[1]
                node1 = ep1.split(":")[0]
                node2 = ep2.split(":")[0]
                lines.append(f"{node1} <----> {node2}")
            return "\n".join(lines)

