"""
Generate Route Redistribution task variations.

Creates tasks that test route redistribution between different routing protocols
(BGP↔OSPF, OSPF↔Static, BGP↔Static, etc.).
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator


def generate_route_redistribution_tasks(platform: str = "frr") -> List[Dict[str, Any]]:
    """
    Generate all route redistribution task variations.
    
    Target: 100+ unique tasks with diverse redistribution scenarios.

    Returns:
        List of task dictionaries
    """
    generator = TopologyGenerator(default_platform=platform)
    tasks = []

    # OSPF to BGP redistribution
    for node_count in [2, 3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_ospf_to_bgp_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute OSPF routes into BGP",
            from_protocol="ospf",
            to_protocol="bgp",
            scenario="ospf_to_bgp",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # BGP to OSPF redistribution
    for node_count in [2, 3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_bgp_to_ospf_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute BGP routes into OSPF",
            from_protocol="bgp",
            to_protocol="ospf",
            scenario="bgp_to_ospf",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Static to OSPF redistribution
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_static_to_ospf_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute static routes into OSPF",
            from_protocol="static",
            to_protocol="ospf",
            scenario="static_to_ospf",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Static to BGP redistribution
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_static_to_bgp_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute static routes into BGP",
            from_protocol="static",
            to_protocol="bgp",
            scenario="static_to_bgp",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Connected to OSPF redistribution
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_connected_to_ospf_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute connected routes into OSPF",
            from_protocol="connected",
            to_protocol="ospf",
            scenario="connected_to_ospf",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Connected to BGP redistribution
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_connected_to_bgp_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute connected routes into BGP",
            from_protocol="connected",
            to_protocol="bgp",
            scenario="connected_to_bgp",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Star topology - redistribute at hub
    for node_count in [3, 4, 5, 6, 8]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_ospf_to_bgp_star_{node_count}n",
            description=f"Star {node_count}-node: Redistribute OSPF to BGP at hub",
            from_protocol="ospf",
            to_protocol="bgp",
            scenario="ospf_to_bgp_star",
            node_count=node_count,
            platform=platform,
            redistribute_node="R1"
        )
        tasks.append(task)

    # Ring topology redistribution
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_ospf_to_bgp_ring_{node_count}n",
            description=f"Ring {node_count}-node: OSPF to BGP redistribution",
            from_protocol="ospf",
            to_protocol="bgp",
            scenario="ospf_to_bgp_ring",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Redistribution with route-map filtering
    for node_count in [2, 3, 4]:
        for filter_type in ["prefix-list", "route-map", "access-list"]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_redistribution_task(
                topology=topo,
                task_id=f"redist_filtered_{filter_type.replace('-', '_')}_{node_count}n",
                description=f"Linear {node_count}-node: Filtered redistribution using {filter_type}",
                from_protocol="ospf",
                to_protocol="bgp",
                scenario=f"filtered_redist_{filter_type.replace('-', '_')}",
                node_count=node_count,
                platform=platform,
                filter_type=filter_type
            )
            tasks.append(task)

    # Redistribution with metric modification
    for node_count in [2, 3, 4]:
        for metric in [10, 100, 1000]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_redistribution_task(
                topology=topo,
                task_id=f"redist_metric_{metric}_{node_count}n",
                description=f"Linear {node_count}-node: Redistribute with metric {metric}",
                from_protocol="ospf",
                to_protocol="bgp",
                scenario=f"metric_redist_{metric}",
                node_count=node_count,
                platform=platform,
                metric=metric
            )
            tasks.append(task)

    # Mutual redistribution (bidirectional)
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_mutual_ospf_bgp_{node_count}n",
            description=f"Linear {node_count}-node: Mutual OSPF↔BGP redistribution",
            from_protocol="ospf",
            to_protocol="bgp",
            scenario="mutual_ospf_bgp",
            node_count=node_count,
            platform=platform,
            mutual=True
        )
        tasks.append(task)

    # Tree topology redistribution
    for depth in [2, 3]:
        for branch in [2, 3]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count_tree = len(topo.nodes)
            
            task = create_redistribution_task(
                topology=topo,
                task_id=f"redist_ospf_to_bgp_tree_d{depth}_b{branch}",
                description=f"Tree d{depth}b{branch} ({node_count_tree} nodes): Redistribution at root",
                from_protocol="ospf",
                to_protocol="bgp",
                scenario=f"ospf_to_bgp_tree_d{depth}_b{branch}",
                node_count=node_count_tree,
                platform=platform
            )
            tasks.append(task)

    # Tag-based redistribution
    for node_count in [2, 3, 4]:
        for tag in [100, 200, 300]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_redistribution_task(
                topology=topo,
                task_id=f"redist_tag_{tag}_{node_count}n",
                description=f"Linear {node_count}-node: Redistribute with route tag {tag}",
                from_protocol="ospf",
                to_protocol="bgp",
                scenario=f"redist_tag_{tag}",
                node_count=node_count,
                platform=platform,
                route_tag=tag
            )
            tasks.append(task)

    # RIP to OSPF redistribution
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_rip_to_ospf_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute RIP routes into OSPF",
            from_protocol="rip",
            to_protocol="ospf",
            scenario="rip_to_ospf",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # RIP to BGP redistribution
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_rip_to_bgp_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute RIP routes into BGP",
            from_protocol="rip",
            to_protocol="bgp",
            scenario="rip_to_bgp",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Mesh topology redistribution
    for node_count in [3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_ospf_to_bgp_mesh_{node_count}n",
            description=f"Mesh {node_count}-node: Redistribution in full mesh",
            from_protocol="ospf",
            to_protocol="bgp",
            scenario="ospf_to_bgp_mesh",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Star with BGP to OSPF
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_bgp_to_ospf_star_{node_count}n",
            description=f"Star {node_count}-node: Redistribute BGP to OSPF at hub",
            from_protocol="bgp",
            to_protocol="ospf",
            scenario="bgp_to_ospf_star",
            node_count=node_count,
            platform=platform,
            redistribute_node="R1"
        )
        tasks.append(task)

    # Kernel routes to OSPF
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_kernel_to_ospf_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute kernel routes into OSPF",
            from_protocol="kernel",
            to_protocol="ospf",
            scenario="kernel_to_ospf",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Kernel routes to BGP
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_kernel_to_bgp_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute kernel routes into BGP",
            from_protocol="kernel",
            to_protocol="bgp",
            scenario="kernel_to_bgp",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Subnets-only redistribution
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_ospf_subnets_to_bgp_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute OSPF subnets to BGP",
            from_protocol="ospf",
            to_protocol="bgp",
            scenario="ospf_subnets_to_bgp",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # ISIS to OSPF redistribution
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_isis_to_ospf_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute ISIS routes into OSPF",
            from_protocol="isis",
            to_protocol="ospf",
            scenario="isis_to_ospf",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # ISIS to BGP redistribution  
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_redistribution_task(
            topology=topo,
            task_id=f"redist_isis_to_bgp_linear_{node_count}n",
            description=f"Linear {node_count}-node: Redistribute ISIS routes into BGP",
            from_protocol="isis",
            to_protocol="bgp",
            scenario="isis_to_bgp",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    return tasks


def create_redistribution_task(
    topology: Any,
    task_id: str,
    description: str,
    from_protocol: str,
    to_protocol: str,
    scenario: str,
    node_count: int,
    platform: str = "frr",
    redistribute_node: str = None,
    filter_type: str = None,
    metric: int = None,
    mutual: bool = False,
    route_tag: int = None
) -> Dict[str, Any]:
    """
    Create a route redistribution task.

    Args:
        topology: TopologySpecification object
        description: Task description
        scenario: Scenario type
        node_count: Number of nodes
        platform: Platform type
        redistribute_node: Node to perform redistribution (default: first)
        filter_type: Type of filter to apply
        metric: Metric value to set
        mutual: If True, redistribute in both directions
        route_tag: Route tag to apply

    Returns:
        Task dictionary
    """
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

    target_node = redistribute_node or topology.nodes[0].name
    
    properties = []
    
    # Determine commands based on platform
    if platform == "nokia_srl":
        # Nokia check: check for export policy in protocol context
        redist_cmd = "sr_cli -e 'info network-instance default protocols'"
        redist_expect = "export-policy" # or policy name, but generic check for now
        
        route_cmd = "sr_cli -e 'show network-instance default route-table ipv4'"
        # Expected protocol code in Nokia route table (e.g. "bgp", "ospf")
        route_expect = to_protocol.lower()
        if to_protocol == "bgp": route_expect = "bgp"
        if to_protocol == "ospf": route_expect = "ospf"
        
    elif platform == "arista_eos":
        redist_cmd = "Cli -c 'show running-config | section redistribute'"
        redist_expect = f"redistribute {from_protocol}"
        route_cmd = f"Cli -c 'show ip route {to_protocol}'"
        route_expect = from_protocol[0].upper() # e.g. "O" or "B" (Arista uses B, O)

    elif platform == "cisco_ios_xe":
        redist_cmd = "cli -c 'show running-config | include redistribute'"
        redist_expect = f"redistribute {from_protocol}"
        route_cmd = f"cli -c 'show ip route {to_protocol}'"
        route_expect = from_protocol[0].upper() # e.g. "O" or "B"

    else: # frr
        redist_cmd = f"vtysh -c 'show running-config' | grep redistribute"
        redist_expect = f"redistribute {from_protocol}"
        route_cmd = f"vtysh -c 'show ip {to_protocol}' 2>/dev/null || vtysh -c 'show ip route {to_protocol}'"
        route_expect = from_protocol[0].upper()

    
    # Primary property: Redistribution is configured
    redist_prop = {
        "id": f"redist_{from_protocol}_to_{to_protocol}",
        "type": "route_redistribution",
        "description": f"Routes from {from_protocol} are redistributed into {to_protocol}",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": target_node,
            "command": redist_cmd,
            "parser": "text",
            "success_condition": {
                "contains_text": redist_expect
            }
        }
    }
    properties.append(redist_prop)

    # Verify routes appear in destination protocol
    route_prop = {
        "id": f"routes_in_{to_protocol}",
        "type": "route_exists",
        "description": f"Redistributed routes appear in {to_protocol} table",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": target_node,
            "command": route_cmd,
            "parser": "text",
            "success_condition": {
                "contains_text": route_expect
            }
        }
    }
    properties.append(route_prop)

    # Estimate command count
    node_count = len(topology.nodes)
    # Base: IPs + protocol configs + redistribution
    base_cmds = node_count * 2  # IPs
    protocol_cmds = node_count * 4  # Basic protocol config per node
    redist_cmds = 2  # Enter protocol, add redistribute
    if filter_type:
        redist_cmds += 3
    if mutual:
        redist_cmds *= 2
    cmd_count = base_cmds + protocol_cmds + redist_cmds

    task = {
        "task_id": task_id,
        "description": description,
        "platform": platform,
        "topology": topo_dict,
        "intent": {
            "properties": properties
        },
        "convergence": {
            "timeout_seconds": 60,  # Longer for protocol convergence
            "check_interval_seconds": 5
        },
        "optimal_solution": {
            "command_count": cmd_count,
            "description": f"Configure {from_protocol}→{to_protocol} redistribution on {node_count} nodes"
        }
    }

    return task
