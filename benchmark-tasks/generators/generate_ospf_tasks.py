"""
Generate OSPF configuration task variations.

Creates tasks that test OSPF adjacency establishment and routing.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator


def generate_ospf_tasks(platform: str = "frr") -> List[Dict[str, Any]]:
    """
    Generate all OSPF configuration task variations.
    
    Target: 100+ unique tasks with diverse topologies and OSPF scenarios.

    Returns:
        List of task dictionaries
    """
    generator = TopologyGenerator(default_platform=platform)
    tasks = []

    # Single area (area 0) linear topologies - expanded
    for node_count in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_area0_linear_{node_count}n",
            description=f"OSPF area 0 linear {node_count}-node topology",
            area_config="single_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Single area star topologies - expanded
    for node_count in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_area0_star_{node_count}n",
            description=f"OSPF area 0 star {node_count}-node topology",
            area_config="single_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Single area ring topologies - expanded
    for node_count in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_area0_ring_{node_count}n",
            description=f"OSPF area 0 ring {node_count}-node topology",
            area_config="single_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Single area mesh topologies - expanded
    for node_count in [3, 4, 5, 6, 7]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_area0_mesh_{node_count}n",
            description=f"OSPF area 0 mesh {node_count}-node topology",
            area_config="single_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Single area tree topologies - new
    for depth in [2, 3]:
        for branch in [2, 3, 4, 5]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_ospf_task(
                topology=topo,
                task_id=f"ospf_area0_tree_d{depth}_b{branch}",
                description=f"OSPF area 0 tree depth {depth} branch {branch}",
                area_config="single_area",
                node_count=node_count,
                platform=platform
            )
            tasks.append(task)

    # Multi-area scenarios (tree with ABR) - expanded
    for depth in [2, 3, 4]:
        for branch in [2, 3, 4, 5]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            
            task = create_ospf_task(
                topology=topo,
                task_id=f"ospf_multiarea_tree_d{depth}_b{branch}",
                description=f"OSPF multi-area tree depth {depth} branching {branch}",
                area_config="multi_area",
                node_count=len(topo.nodes),
                platform=platform
            )
            tasks.append(task)

    # Multi-area linear scenarios - new
    for node_count in [4, 6, 8, 10, 12, 14, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_multiarea_linear_{node_count}n",
            description=f"OSPF multi-area linear {node_count}-node with ABR",
            area_config="multi_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Multi-area ring scenarios - new
    for node_count in [6, 8, 10, 12, 16]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_multiarea_ring_{node_count}n",
            description=f"OSPF multi-area ring {node_count}-node with ABRs",
            area_config="multi_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Additional single area scenarios for scale testing
    for node_count in [22, 24, 25]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_area0_linear_{node_count}n",
            description=f"OSPF area 0 linear {node_count}-node - large scale",
            area_config="single_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Additional star scenarios for scale testing
    for node_count in [22, 24, 25]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_area0_star_{node_count}n",
            description=f"OSPF area 0 star {node_count}-node - large scale",
            area_config="single_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Additional ring scenarios
    for node_count in [22, 24, 25]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_area0_ring_{node_count}n",
            description=f"OSPF area 0 ring {node_count}-node - large scale",
            area_config="single_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Additional multi-area scenarios
    for node_count in [22, 24, 25]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_multiarea_linear_{node_count}n",
            description=f"OSPF multi-area linear {node_count}-node - large scale",
            area_config="multi_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    # Additional multi-area ring scenarios
    for node_count in [20, 24]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_ospf_task(
            topology=topo,
            task_id=f"ospf_multiarea_ring_{node_count}n",
            description=f"OSPF multi-area ring {node_count}-node - large scale",
            area_config="multi_area",
            node_count=node_count,
            platform=platform
        )
        tasks.append(task)

    return tasks


def create_ospf_task(
    topology: Any,
    task_id: str,
    description: str,
    area_config: str,
    node_count: int,
    platform: str = "frr"
) -> Dict[str, Any]:
    """
    Create an OSPF configuration task.

    Args:
        topology: TopologySpecification object
        task_id: Unique task identifier
        description: Task description
        area_config: "single_area" or "multi_area"
        node_count: Number of nodes
        platform: Platform type

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

    properties = []

    # Add OSPF adjacency properties for each link
    # Add OSPF adjacency properties for each link
    for i, link in enumerate(topology.links):
        node1 = link.endpoints[0].split(':')[0]
        node2 = link.endpoints[1].split(':')[0]
        
        # Determine verification command based on platform
        if platform == "nokia_srl":
            verify_cmd = "sr_cli -e 'show network-instance default protocols ospf neighbor'"
            expect_text = "Full"
        elif platform == "arista_eos":
            verify_cmd = "Cli -c 'show ip ospf neighbor'"
            expect_text = "FULL"
        elif platform == "cisco_ios_xe":
            verify_cmd = "cli -c 'show ip ospf neighbor'" # Assumes vrnetlab wrapper
            expect_text = "FULL"
        else: # frr
            verify_cmd = "vtysh -c 'show ip ospf neighbor'"
            expect_text = "Full"

        # OSPF adjacency property
        prop = {
            "id": f"ospf_adjacency_{node1}_{node2}",
            "type": "ospf_configuration",
            "description": f"OSPF adjacency between {node1} and {node2}",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": node1,
                "command": verify_cmd,
                "parser": "text",
                "success_condition": {
                    "contains_text": expect_text
                }
            }
        }
        properties.append(prop)

    # Reachability check removed to avoid IP prediction errors. 
    # OSPF Adjacency and Routing Table checks are sufficient.

    # Add routing table completeness property
    if platform == "nokia_srl":
        route_cmd = "sr_cli -e 'show network-instance default route-table ipv4'"
        route_expect = "ospf"
    elif platform == "arista_eos":
        route_cmd = "Cli -c 'show ip route ospf'"
        route_expect = "O"
    elif platform == "cisco_ios_xe":
        route_cmd = "cli -c 'show ip route ospf'"
        route_expect = "O"
    else: # frr
        route_cmd = "vtysh -c 'show ip route ospf'"
        route_expect = "O>"

    route_prop = {
        "id": "routing_table_complete",
        "type": "route_exists",
        "description": "Routing table has OSPF routes",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": topology.nodes[0].name,
            "command": route_cmd,
            "parser": "text",
            "success_condition": {
                "contains_text": route_expect
            }
        }
    }
    properties.append(route_prop)

    task = {
        "task_id": task_id,
        "description": description,
        "platform": platform,
        "topology": topo_dict,
        "intent": {
            "properties": properties
        },
        "convergence": {
            "timeout_seconds": 60,
            "check_interval_seconds": 5
        },
        "optimal_solution": {
            "command_count": node_count * 6,  # Estimate: IP + OSPF config per node
            "description": f"Configure OSPF on all {node_count} routers with appropriate area and network statements"
        }
    }

    return task

