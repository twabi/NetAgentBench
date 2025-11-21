"""
LLM task presenter for formatting tasks for LLM consumption.

Formats benchmark tasks as clear prompts with topology information,
success criteria, and response format instructions.
"""
from typing import Optional
from benchmark.models.task import TaskDefinition


class LLMTaskPresenter:
    """
    Formats benchmark tasks for LLM consumption.
    
    Creates structured prompts that include:
    - Task description and context
    - Network topology details
    - Success criteria
    - Expected response format
    """

    def format_task_for_llm(
        self,
        task: TaskDefinition,
        task_index: Optional[int] = None,
        total_tasks: Optional[int] = None,
    ) -> str:
        """
        Format a task as a prompt for an LLM.
        
        Args:
            task: TaskDefinition to format
            task_index: Optional task number in sequence
            total_tasks: Optional total number of tasks
        
        Returns:
            Formatted prompt string for the LLM
        """
        lines = []

        # Header with context
        if task_index is not None and total_tasks is not None:
            lines.append(f"# Network Configuration Task {task_index}/{total_tasks}")
        else:
            lines.append("# Network Configuration Task")
        lines.append("")

        # Task information
        lines.append(f"## Task ID: {task.task_id}")
        lines.append(f"## Description: {task.description}")
        platform_str = task.platform.value if hasattr(task.platform, "value") else str(task.platform)
        lines.append(f"## Platform: {platform_str}")
        lines.append("")

        # Topology
        lines.append("## Network Topology")
        lines.append("")
        lines.append(self._format_topology(task))
        lines.append("")

        # Success criteria
        lines.append("## Success Criteria")
        lines.append("")
        lines.append("You need to configure the network to satisfy these properties:")
        lines.append("")
        for i, prop in enumerate(task.intent.properties, 1):
            lines.append(f"{i}. **{prop.description}**")
            lines.append(f"   - Type: {prop.type}")
            lines.append(f"   - Verification: {prop.evaluation.command}")
        lines.append("")

        # Configuration requirements
        lines.append("## Configuration Requirements")
        lines.append("")
        lines.append(f"- Platform: {platform_str}")
        if task.convergence:
            lines.append(f"- Convergence timeout: {task.convergence.timeout_seconds} seconds")
        lines.append("")
        
        # Configuration guidelines (NEW - addressing LLM over-engineering)
        lines.append("## Configuration Guidelines")
        lines.append("")
        lines.append("**IMPORTANT - Use the Simplest Approach:**")
        lines.append("")
        lines.append("- **Prefer simplicity**: Use the most straightforward solution that satisfies requirements")
        lines.append("- **Static routes first**: Use static routes (`ip route add`) unless dynamic routing is explicitly required")
        lines.append("- **Avoid routing protocols**: Do NOT use OSPF, BGP, or other protocols unless the task specifically asks for them")
        lines.append("- **Use Linux `ip` commands**: Prefer `ip link`, `ip addr`, `ip route` over vtysh/FRR commands")
        lines.append("- **Enable IP forwarding**: Use `sysctl -w net.ipv4.ip_forward=1` for multi-hop connectivity")
        lines.append("- **Test your approach**: Think about whether your commands will actually work in this environment")
        lines.append("")
        
        # Example approach (NEW - showing what works)
        lines.append("## Example Approach (for reference)")
        lines.append("")
        lines.append("For a typical reachability task between R1 and R3 in a linear topology:")
        lines.append("")
        lines.append("```bash")
        lines.append("# R1: Configure interface and route")
        lines.append("ip link set dev eth1 up")
        lines.append("ip addr add 10.0.1.1/30 dev eth1")
        lines.append("ip route add 192.168.3.3/32 via 10.0.1.2")
        lines.append("")
        lines.append("# R2: Configure interfaces, enable forwarding, add routes")
        lines.append("sysctl -w net.ipv4.ip_forward=1")
        lines.append("ip link set dev eth1 up")
        lines.append("ip addr add 10.0.1.2/30 dev eth1")
        lines.append("ip link set dev eth2 up")
        lines.append("ip addr add 10.0.2.1/30 dev eth2")
        lines.append("ip route add 192.168.3.3/32 via 10.0.2.2")
        lines.append("")
        lines.append("# R3: Configure interface and loopback")
        lines.append("ip link set dev eth1 up")
        lines.append("ip addr add 10.0.2.2/30 dev eth1")
        lines.append("ip addr add 192.168.3.3/32 dev lo")
        lines.append("```")
        lines.append("")
        lines.append("This simple approach using static routes is often MORE reliable than complex routing protocols.")
        lines.append("")
        
        # Common pitfalls (NEW - warnings)
        lines.append("## Common Pitfalls to Avoid")
        lines.append("")
        lines.append("**DO NOT:**")
        lines.append("- Use `vtysh` commands unless absolutely necessary (they often fail)")
        lines.append("- Configure OSPF/BGP for simple reachability tasks (overkill and error-prone)")
        lines.append("- Assume FRR daemons are running (they may not be)")
        lines.append("- Over-complicate the solution with unnecessary services")
        lines.append("")
        lines.append("**DO:**")
        lines.append("- Use basic Linux networking commands (`ip`, `sysctl`)")
        lines.append("- Configure static routes for predictable paths")
        lines.append("- Keep commands simple and direct")
        lines.append("- Enable IP forwarding on intermediate routers")
        lines.append("")

        # Response format
        lines.append("## Expected Response Format")
        lines.append("")
        lines.append("Provide your solution as a JSON object with this **exact** structure:")
        lines.append("")
        lines.append("```json")
        lines.append("{")
        lines.append('  "approach": {')
        lines.append('    "description": "Brief description of your configuration strategy",')
        lines.append('    "commands": [')
        lines.append("      {")
        lines.append('        "node": "R1",')
        lines.append('        "commands": [')
        lines.append('          "command1",')
        lines.append('          "command2"')
        lines.append("        ]")
        lines.append("      },")
        lines.append("      {")
        lines.append('        "node": "R2",')
        lines.append('        "commands": ["command3"]')
        lines.append("      }")
        lines.append("    ]")
        lines.append("  }")
        lines.append("}")
        lines.append("```")
        lines.append("")
        lines.append("**Important:**")
        lines.append("- Provide configuration commands for each node in the topology")
        lines.append("- Commands should be executable on the specified platform")
        lines.append("- Commands will be executed in the order specified")
        lines.append("")
        lines.append("**IMPORTANT**: Your response MUST contain valid JSON. You can:")
        lines.append("- Return ONLY the JSON object")
        lines.append("- Include the JSON in a ```json code block")
        lines.append("- Include explanatory text BEFORE or AFTER the JSON, but JSON must be present")
        lines.append("")

        return "\n".join(lines)

    def _format_topology(self, task: TaskDefinition) -> str:
        """
        Format topology as readable text.
        
        Args:
            task: TaskDefinition with topology
        
        Returns:
            Formatted topology description
        """
        lines = []

        # Nodes
        lines.append(f"**Nodes ({len(task.topology.nodes)}):**")
        for node in task.topology.nodes:
            node_type = node.type.value if hasattr(node.type, "value") else str(node.type)
            node_platform = node.platform.value if hasattr(node.platform, "value") else str(node.platform)
            lines.append(f"- {node.name}: {node_type} ({node_platform})")

        lines.append("")

        # Links
        lines.append(f"**Links ({len(task.topology.links)}):**")
        for link in task.topology.links:
            ep1, ep2 = link.endpoints
            lines.append(f"- {ep1} ↔ {ep2}")

        lines.append("")

        # Topology diagram
        lines.append("**Topology Diagram:**")
        lines.append("```")
        lines.append(self._generate_topology_diagram(task))
        lines.append("```")

        return "\n".join(lines)

    def _generate_topology_diagram(self, task: TaskDefinition) -> str:
        """
        Generate a simple ASCII topology diagram.
        
        Args:
            task: TaskDefinition with topology
        
        Returns:
            ASCII diagram
        """
        nodes = [node.name for node in task.topology.nodes]

        if len(nodes) == 2:
            return f"{nodes[0]} -------- {nodes[1]}"
        elif len(nodes) == 3 and len(task.topology.links) == 2:
            return f"{nodes[0]} ----- {nodes[1]} ----- {nodes[2]}"
        else:
            # Generic: list connections
            lines = []
            for link in task.topology.links:
                ep1, ep2 = link.endpoints[0], link.endpoints[1]
                node1 = ep1.split(":")[0]
                node2 = ep2.split(":")[0]
                lines.append(f"{node1} <----> {node2}")
            return "\n".join(lines)

