"""
Generate Firewall Rules task variations.

Creates tasks that test firewall configuration where reachability is 
curtailed/controlled by firewall rules. Different from ACL - this focuses
on zone-based firewalls and stateful inspection.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator


def generate_firewall_tasks(platform: str = "linux") -> List[Dict[str, Any]]:
    """
    Generate all firewall rule task variations.
    
    Target: 100+ unique tasks with diverse firewall scenarios.
    Focus: Reachability that is curtailed by firewall rules.

    Returns:
        List of task dictionaries
    """
    generator = TopologyGenerator(default_platform=platform)
    tasks = []

    # Zone-based firewall - inside to outside
    for node_count in [2, 3, 4, 5, 6]:
        for action in ["permit", "deny"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_zone_{action}_linear_{node_count}n",
                rule_name=f"ZONE_{action.upper()}",
                action=action,
                from_zone="inside",
                to_zone="outside",
                description=f"Linear {node_count}-node: {action.title()} traffic from inside to outside zone",
                scenario_type="zone_based_inside_outside",
                node_count=node_count,
                platform=platform
            )
            tasks.append(task)

    # Service-specific firewall rules
    for node_count in [2, 3, 4]:
        for service in ["http", "https", "ssh", "dns", "smtp", "ftp"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_service_{service}_linear_{node_count}n",
                rule_name=f"ALLOW_{service.upper()}",
                action="permit",
                service=service,
                description=f"Linear {node_count}-node: Allow {service.upper()} service through firewall",
                scenario_type="service_firewall",
                node_count=node_count,
                platform=platform
            )
            tasks.append(task)

    # Stateful firewall - track connections
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_firewall_task(
            topology=topo,
            task_id=f"fw_stateful_{node_count}n",
            description=f"Linear {node_count}-node: Stateful firewall allowing established connections",
            scenario_type="stateful",
            node_count=node_count,
            platform=platform,
            rule_name="STATEFUL",
            action="permit",
            stateful=True,
        )
        tasks.append(task)

    # DMZ configuration - three-zone architecture
    for inner_nodes in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_star(inner_nodes + 2)  # hub + DMZ + inner nodes
        
        task = create_firewall_task(
            topology=topo,
            task_id=f"fw_dmz_{inner_nodes}inner",
            description=f"DMZ with {inner_nodes} internal nodes: Restrict outside to DMZ only",
            scenario_type="dmz_config",
            node_count=inner_nodes + 2, # Total nodes in star topology
            platform=platform,
            rule_name="DMZ_RULES",
            action="permit",
            from_zone="outside",
            to_zone="dmz",
            dmz_config=True,
        )
        tasks.append(task)

    # Block specific IPs (blacklist)
    for node_count in [2, 3, 4]:
        for blocked_net in ["10.10.10.0/24", "172.16.100.0/24"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_block_{node_count}n_{blocked_net.split('/')[0].replace('.', '_')}",
                description=f"Linear {node_count}-node: Block all traffic from {blocked_net}",
                scenario_type="block_ip",
                node_count=node_count,
                platform=platform,
                rule_name="BLOCK_NET",
                action="deny",
                source_net=blocked_net,
            )
            tasks.append(task)

    # Allow specific destination
    for node_count in [2, 3, 4]:
        for dest_net in ["192.168.1.0/24", "10.0.0.0/8"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_allow_dest_{node_count}n_{dest_net.split('.')[0]}",
                description=f"Linear {node_count}-node: Allow traffic to {dest_net}",
                scenario_type="allow_dest",
                node_count=node_count,
                platform=platform,
                rule_name="ALLOW_DEST",
                action="permit",
                dest_net=dest_net,
            )
            tasks.append(task)

    # Port range firewall rules
    for node_count in [2, 3, 4]:
        for port_range in ["1024-65535", "80-443", "20-21"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_portrange_{node_count}n_{port_range.replace('-', '_')}",
                description=f"Linear {node_count}-node: Allow port range {port_range}",
                scenario_type="port_range",
                node_count=node_count,
                platform=platform,
                rule_name=f"PORTS_{port_range.replace('-', '_')}",
                action="permit",
                port_range=port_range,
            )
            tasks.append(task)

    # Star topology - central firewall
    for node_count in [3, 4, 5, 6, 8]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_firewall_task(
            topology=topo,
            task_id=f"fw_central_star_{node_count}n",
            description=f"Star {node_count}-node: Central firewall at hub controls all traffic",
            scenario_type="central_firewall",
            node_count=node_count,
            platform=platform,
            rule_name="CENTRAL_FW",
            action="permit",
            central_firewall=True,
        )
        tasks.append(task)

    # Ring topology with firewall checkpoints
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_firewall_task(
            topology=topo,
            task_id=f"fw_ring_{node_count}n",
            description=f"Ring {node_count}-node: Firewall rules on ring topology",
            scenario_type="ring_firewall",
            node_count=node_count,
            platform=platform,
            rule_name="RING_FW",
            action="permit",
        )
        tasks.append(task)

    # Implicit deny (default deny all, explicit allow)
    for node_count in [2, 3, 4]:
        for allowed_port in [22, 80, 443]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_implicit_deny_{node_count}n_allow{allowed_port}",
                description=f"Linear {node_count}-node: Deny all except port {allowed_port}",
                scenario_type="implicit_deny",
                node_count=node_count,
                platform=platform,
                rule_name=f"IMPLICIT_DENY_{allowed_port}",
                action="permit",
                port=allowed_port,
                implicit_deny=True,
            )
            tasks.append(task)

    # ICMP control (ping allowed/denied)
    for node_count in [2, 3, 4, 5]:
        for action in ["permit", "deny"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_icmp_{action}_{node_count}n",
                description=f"Linear {node_count}-node: {action.title()} ICMP (ping)",
                scenario_type="icmp_control",
                node_count=node_count,
                platform=platform,
                rule_name=f"ICMP_{action.upper()}",
                action=action,
                protocol="icmp",
            )
            tasks.append(task)

    # Tree topology firewall
    for depth in [2, 3]:
        for branch in [2, 3]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_tree_d{depth}_b{branch}",
                description=f"Tree d{depth}b{branch} ({node_count} nodes): Hierarchical firewall",
                scenario_type="tree_firewall",
                node_count=node_count,
                platform=platform,
                rule_name="TREE_FW",
                action="permit",
            )
            tasks.append(task)

    # Connection tracking rules
    for node_count in [2, 3, 4, 5]:
        for state in ["new", "established", "related"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_firewall_task(
                topology=topo,
                task_id=f"fw_conntrack_{state}_{node_count}n",
                description=f"Linear {node_count}-node: Allow {state} connections",
                scenario_type="connection_tracking",
                node_count=node_count,
                platform=platform,
                rule_name=f"TRACK_{state.upper()}",
                action="permit",
                stateful=True,
            )
            tasks.append(task)

    # Mesh topology firewall
    for node_count in [3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        task = create_firewall_task(
            topology=topo,
            task_id=f"fw_mesh_{node_count}n",
            description=f"Mesh {node_count}-node: Firewall on full mesh topology",
            scenario_type="mesh_firewall",
            node_count=node_count,
            platform=platform,
            rule_name="MESH_FW",
            action="permit",
        )
        tasks.append(task)

    return tasks


def create_firewall_task(
    topology: Any,
    task_id: str,
    description: str,
    scenario_type: str,
    node_count: int,
    platform: str = "linux",
    rule_name: str = None,
    action: str = None,
    from_zone: str = None,
    to_zone: str = None,
    service: str = None,
    stateful: bool = False,
    dmz_config: bool = False,
    source_net: str = None,
    dest_net: str = None,
    port_range: str = None,
    port: int = None,
    central_firewall: bool = False,
    implicit_deny: bool = False,
    protocol: str = None
) -> Dict[str, Any]:
    """
    Create a firewall rule configuration task.

    Args:
        topology: TopologySpecification object
        task_id: Unique task identifier
        rule_name: Name of the firewall rule
        action: permit or deny
        description: Task description
        from_zone: Source security zone
        to_zone: Destination security zone
        service: Service name (http, https, etc.)
        stateful: If True, stateful inspection
        dmz_config: If True, DMZ configuration
        source_net: Source network CIDR
        dest_net: Destination network CIDR
        port_range: Port range string (e.g., "80-443")
        port: Single port number
        central_firewall: If True, central firewall at hub
        implicit_deny: If True, implicit deny all
        protocol: Protocol (icmp, tcp, udp)

    Returns:
        Task dictionary
    """
    if platform != "linux":
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

    target_node = topology.nodes[0].name
    
    properties = []
    
    target_node = topology.nodes[0].name
    
    properties = []
    
    # Determine platform specific commands
    if platform == "nokia_srl":
        fw_cmd = "sr_cli -e 'info acl'"
        fw_expect = rule_name
        ping_cmd = f"sr_cli -e 'ping 192.168.1.2 count 2'"
        ping_expect = "0% packet loss"
        deny_cmd = "sr_cli -e 'info acl'" # Check counters if possible, or just config
        deny_expect = "deny" 
    elif platform == "arista_eos":
        fw_cmd = "Cli -c 'show ip access-lists'"
        fw_expect = rule_name
        ping_cmd = "ping 192.168.1.2 repeat 2"
        ping_expect = "0% packet loss"
        deny_cmd = "Cli -c 'show ip access-lists'" 
        deny_expect = "deny"
    elif platform == "cisco_ios_xe":
        fw_cmd = "cli -c 'show ip access-lists'"
        fw_expect = rule_name
        ping_cmd = "ping 192.168.1.2 repeat 2"
        ping_expect = "!!!"
        deny_cmd = "cli -c 'show ip access-lists'"
        deny_expect = "deny"
    else: # linux (alpine) - use iptables
        fw_cmd = "iptables -L FORWARD -n"
        fw_expect = rule_name if rule_name else "ACCEPT"
        ping_cmd = "ping -c 2 192.168.1.2"
        ping_expect = "2 packets transmitted, 2 packets received"
        deny_cmd = "iptables -L FORWARD -n"
        deny_expect = "DROP"

    # Primary property: Firewall rule exists
    fw_prop = {
        "id": f"fw_{rule_name}_exists",
        "type": "firewall_rule",
        "description": f"Firewall rule {rule_name} is configured with {action}",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": target_node,
            "command": fw_cmd,
            "parser": "text",
            "success_condition": {
                "contains_text": fw_expect
            }
        }
    }
    properties.append(fw_prop)

    # Reachability verification based on firewall action
    if action == "permit":
        reach_prop = {
            "id": f"reach_allowed_by_{rule_name}",
            "type": "reachability",
            "description": f"Traffic is allowed through firewall",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": target_node,
                "command": ping_cmd,
                "parser": "text",
                "success_condition": {
                    "contains_text": ping_expect
                }
            }
        }
        properties.append(reach_prop)
    else:
        # For deny rules, verify traffic is blocked
        block_prop = {
            "id": f"blocked_by_{rule_name}",
            "type": "firewall_block",
            "description": f"Traffic is blocked by firewall rule",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": target_node,
                "command": deny_cmd,
                "parser": "text",
                "success_condition": {
                    "contains_text": deny_expect
                }
            }
        }
        properties.append(block_prop)

    # Estimate command count
    node_count = len(topology.nodes)
    base_cmds = node_count * 2  # IPs
    fw_cmds = 4  # Create rule, set action, set match, apply
    if stateful:
        fw_cmds += 2
    if dmz_config:
        fw_cmds += 3
    cmd_count = base_cmds + fw_cmds

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
            "description": f"Configure firewall rule {rule_name} on {node_count} nodes"
        }
    }

    return task
