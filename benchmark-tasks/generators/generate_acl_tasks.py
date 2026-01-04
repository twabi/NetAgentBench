"""
Generate ACL (Access Control List) configuration task variations.

Creates tasks that test ACL/firewall rule configuration for traffic filtering.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator


def generate_acl_tasks(platform: str = "linux") -> List[Dict[str, Any]]:
    """
    Generate all ACL configuration task variations.
    
    Target: 100+ unique tasks with diverse ACL scenarios.

    Returns:
        List of task dictionaries
    """
    generator = TopologyGenerator(default_platform=platform)
    tasks = []

    # Basic permit rules - linear topologies (expanded)
    for node_count in [2, 3, 4, 5, 6]:
        for protocol in ["icmp", "tcp", "udp", "ip"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_acl_task(
                topology=topo,
                task_id=f"acl_permit_{protocol}_linear_{node_count}n",
                acl_name=f"PERMIT_{protocol.upper()}",
                description=f"Linear {node_count}-node: Permit {protocol.upper()} traffic",
                acl_rules=[{"action": "permit", "protocol": protocol}],
                platform=platform
            )
            tasks.append(task)

    # Basic deny rules (expanded)
    for node_count in [2, 3, 4, 5]:
        for protocol in ["icmp", "tcp", "udp"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_acl_task(
                topology=topo,
                task_id=f"acl_deny_{protocol}_linear_{node_count}n",
                acl_name=f"DENY_{protocol.upper()}",
                description=f"Linear {node_count}-node: Deny {protocol.upper()} traffic",
                acl_rules=[{"action": "deny", "protocol": protocol}],
                platform=platform
            )
            tasks.append(task)

    # Port-specific ACLs (expanded ports and nodes)
    for node_count in [2, 3, 4, 5]:
        for port in [22, 80, 443, 8080, 3306, 5432, 6379, 27017]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_acl_task(
                topology=topo,
                task_id=f"acl_port{port}_linear_{node_count}n",
                acl_name=f"PERMIT_PORT{port}",
                description=f"Linear {node_count}-node: Permit TCP port {port}",
                acl_rules=[{"action": "permit", "protocol": "tcp", "dest_port": port}],
                platform=platform
            )
            tasks.append(task)

    # Source IP filtering (expanded)
    for node_count in [2, 3, 4, 5]:
        for src_net in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_acl_task(
                topology=topo,
                task_id=f"acl_srcip_linear_{node_count}n_{src_net.split('/')[0].replace('.', '_')}",
                acl_name="FILTER_SRC",
                description=f"Linear {node_count}-node: Permit traffic from {src_net}",
                acl_rules=[{"action": "permit", "protocol": "ip", "source_net": src_net}],
                platform=platform
            )
            tasks.append(task)

    # Destination IP filtering (expanded)
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_acl_task(
            topology=topo,
            task_id=f"acl_dstip_linear_{node_count}n",
            acl_name="FILTER_DST",
            description=f"Linear {node_count}-node: Deny traffic to 192.168.100.0/24",
            acl_rules=[{"action": "deny", "protocol": "ip", "dest_net": "192.168.100.0/24"}],
            platform=platform
        )
        tasks.append(task)

    # Star topology - apply ACL at hub (expanded)
    for node_count in [3, 4, 5, 6, 8, 10]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_acl_task(
            topology=topo,
            task_id=f"acl_hub_star_{node_count}n",
            acl_name="HUB_FILTER",
            description=f"Star {node_count}-node: Apply ACL at hub R1",
            acl_rules=[{"action": "permit", "protocol": "icmp"}],
            apply_node="R1",
            platform=platform
        )
        tasks.append(task)

    # Extended ACL - source + dest + port (expanded)
    for node_count in [2, 3, 4]:
        for port in [22, 80, 443, 8080]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_acl_task(
                topology=topo,
                task_id=f"acl_extended_{node_count}n_port{port}",
                acl_name=f"EXT_ACL_{port}",
                description=f"Linear {node_count}-node: Extended ACL for TCP/{port}",
                acl_rules=[{
                    "action": "permit",
                    "protocol": "tcp",
                    "source_net": "10.0.0.0/24",
                    "dest_net": "192.168.0.0/24",
                    "dest_port": port
                }],
                platform=platform
            )
            tasks.append(task)

    # Bidirectional ACL rules (expanded)
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_acl_task(
            topology=topo,
            task_id=f"acl_bidir_{node_count}n",
            acl_name="BIDIR_FILTER",
            description=f"Linear {node_count}-node: Bidirectional traffic filtering",
            acl_rules=[{"action": "permit", "protocol": "tcp", "bidirectional": True}],
            platform=platform
        )
        tasks.append(task)

    # Ring topology ACL (expanded)
    for node_count in [3, 4, 5, 6, 8]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_acl_task(
            topology=topo,
            task_id=f"acl_ring_{node_count}n",
            acl_name="RING_FILTER",
            description=f"Ring {node_count}-node: ACL applied on ring topology",
            acl_rules=[{"action": "permit", "protocol": "icmp"}],
            platform=platform
        )
        tasks.append(task)

    # Tree topology ACL
    for depth in [2, 3]:
        for branch in [2, 3]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_acl_task(
                topology=topo,
                task_id=f"acl_tree_d{depth}_b{branch}",
                acl_name="TREE_FILTER",
                description=f"Tree d{depth}b{branch} ({node_count} nodes): ACL at root",
                acl_rules=[{"action": "permit", "protocol": "tcp"}],
                platform=platform
            )
            tasks.append(task)

    # Deny all except specific port
    for port in [22, 80, 443]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(3)
        
        task = create_acl_task(
            topology=topo,
            task_id=f"acl_deny_except_{port}",
            acl_name=f"DENY_EXCEPT_{port}",
            description=f"Deny all except TCP/{port} (whitelist approach)",
            acl_rules=[
                {"action": "permit", "protocol": "tcp", "dest_port": port},
                {"action": "deny", "protocol": "ip"}
            ],
            platform=platform
        )
        tasks.append(task)

    return tasks


def create_acl_task(
    topology: Any,
    task_id: str,
    acl_name: str,
    description: str,
    acl_rules: List[Dict[str, Any]],
    platform: str = "linux",
    apply_node: str = None,
) -> Dict[str, Any]:
    """
    Create an ACL configuration task.

    Args:
        topology: TopologySpecification object
        task_id: Unique task identifier
        acl_name: Name of the ACL
        description: Task description
        acl_rules: List of dictionaries, each defining an ACL rule (action, protocol, source_net, dest_net, dest_port, bidirectional)
        platform: The platform for the task (e.g., "frr")
        apply_node: Node to apply ACL on (default: first node)

    Returns:
        Task dictionary
    """
    if platform != "frr":
        task_id = f"{task_id}_{platform}"

    # Convert topology to dict
    topo_dict = {
        "nodes": [
            {
                "name": node.name,
                "type": node.type,
                "image": node.image,
                "platform": node.platform,
            }
            for node in topology.nodes
        ],
        "links": [
            {"endpoints": link.endpoints}
            for link in topology.links
        ],
        "interfaces": []
    }

    target_node = apply_node or topology.nodes[0].name
    
    properties = []
    
    # Platform specific commands
    if platform == "nokia_srl":
        acl_cmd = "sr_cli -e 'info acl'"
        acl_expect = acl_name
    elif platform == "arista_eos":
        acl_cmd = "Cli -c 'show ip access-lists'"
        acl_expect = acl_name
    elif platform == "cisco_ios_xe":
        acl_cmd = "cli -c 'show ip access-lists'"
        acl_expect = acl_name
    elif platform == "linux":
        # Check iptables chain or rule existence
        # Using concise list. Assuming ACL name maps to a Chain or just checking rules in INPUT/FORWARD
        # Simplified: Check if rules exist in FORWARD chain that match the intent
        # iptables uses ACCEPT/DROP, not PERMIT/DENY
        action_map = {"permit": "ACCEPT", "deny": "DROP"}
        target_action = action_map.get(acl_rules[0]['action'].lower(), "ACCEPT")
        acl_cmd = f"sh -c 'iptables -L FORWARD -n | grep \"{target_action}\"'" 
        acl_expect = target_action 
    else: # frr
        acl_cmd = f"vtysh -c 'show running-config' | grep '{acl_name}'"
        acl_expect = acl_name

    # Primary property: ACL exists
    acl_prop = {
        "id": f"acl_{acl_name}_exists",
        "type": "acl_configuration",
        "description": f"ACL {acl_name} is configured",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": target_node,
            "command": acl_cmd,
            "parser": "text",
            "success_condition": {
                "contains_text": acl_expect
            }
        }
    }
    properties.append(acl_prop)

    # Add properties for each rule
    for i, rule in enumerate(acl_rules):
        action = rule.get("action", "permit")
        protocol = rule.get("protocol", "ip")
        source_net = rule.get("source_net")
        dest_net = rule.get("dest_net")
        dest_port = rule.get("dest_port")
        bidirectional = rule.get("bidirectional", False)

        rule_desc = f"{action} {protocol}"
        if source_net:
            rule_desc += f" from {source_net}"
        if dest_net:
            rule_desc += f" to {dest_net}"
        if dest_port:
            rule_desc += f" port {dest_port}"
        if bidirectional:
            rule_desc += " (bidirectional)"

        rule_prop = {
            "id": f"acl_{acl_name}_rule_{i}",
            "type": "acl_rule",
            "description": f"ACL {acl_name} contains rule: {rule_desc}",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": target_node,
                "command": f"sh -c 'iptables -L FORWARD -n | grep \"{dest_port or protocol.lower()}\"'" if platform == "linux" else f"vtysh -c 'show running-config' | grep '{acl_name}'",
                "parser": "text",
                "success_condition": {
                    "contains_text": str(dest_port) if (platform == "linux" and dest_port) else (protocol.lower() if platform == "linux" else action)
                }
            }
        }
        properties.append(rule_prop)

    # Interface application verification
    interface_prop = {
        "id": f"acl_{acl_name}_applied",
        "type": "acl_interface_binding",
        "description": f"ACL is applied to interface",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": target_node,
            "command": "sh -c 'iptables -L FORWARD -n'" if platform == "linux" else "vtysh -c 'show running-config'",
            "parser": "text",
            "success_condition": {
                "contains_text": "Chain FORWARD" if platform == "linux" else f"access-group {acl_name}"
            }
        }
    }
    properties.append(interface_prop)

    # Estimate command count
    node_count = len(topology.nodes)
    base_cmds = node_count * 2  # IPs
    acl_cmds = 3  # Create ACL, add rule, apply to interface
    if bidirectional:
        acl_cmds *= 2
    cmd_count = base_cmds + acl_cmds

    task = {
        "task_id": task_id,
        "description": description,
        "platform": platform,
        "topology": topo_dict,
        "intent": {
            "properties": properties
        },
        "convergence": {
            "timeout_seconds": 30,
            "check_interval_seconds": 2
        },
        "optimal_solution": {
            "command_count": cmd_count,
            "description": f"Configure ACL {acl_name} with {action} {protocol} on {node_count} nodes"
        }
    }

    return task
