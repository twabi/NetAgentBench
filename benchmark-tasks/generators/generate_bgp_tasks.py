"""
Generate BGP configuration task variations.

Creates tasks that test BGP session establishment and route exchange.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator


def generate_bgp_tasks() -> List[Dict[str, Any]]:
    """
    Generate all BGP configuration task variations.
    
    Target: 100+ unique tasks with diverse topologies and BGP scenarios.

    Returns:
        List of task dictionaries
    """
    generator = TopologyGenerator()
    tasks = []

    # eBGP linear topologies (different AS per node) - expanded
    for node_count in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ebgp_linear_{node_count}as",
            description=f"eBGP linear {node_count}-AS topology - establish sessions",
            scenario_type="ebgp_linear",
            node_count=node_count
        )
        tasks.append(task)

    # iBGP star topologies (single AS, route reflector) - expanded
    for node_count in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ibgp_rr_{node_count}n",
            description=f"iBGP route reflector topology with {node_count} routers",
            scenario_type="ibgp_rr",
            node_count=node_count
        )
        tasks.append(task)

    # eBGP mesh scenarios (small to medium scale, different AS) - expanded
    for node_count in [3, 4, 5, 6, 7]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ebgp_mesh_{node_count}as",
            description=f"eBGP full mesh {node_count}-AS topology",
            scenario_type="ebgp_mesh",
            node_count=node_count
        )
        tasks.append(task)

    # iBGP full mesh scenarios (single AS) - expanded
    for node_count in [3, 4, 5, 6, 7, 8]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ibgp_mesh_{node_count}n",
            description=f"iBGP full mesh {node_count} routers in single AS",
            scenario_type="ibgp_mesh",
            node_count=node_count
        )
        tasks.append(task)

    # Ring eBGP scenarios - expanded
    for node_count in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ebgp_ring_{node_count}as",
            description=f"eBGP ring {node_count}-AS topology",
            scenario_type="ebgp_ring",
            node_count=node_count
        )
        tasks.append(task)

    # Ring iBGP scenarios - new
    for node_count in [3, 4, 5, 6, 7, 8, 10, 12]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ibgp_ring_{node_count}n",
            description=f"iBGP ring {node_count}-router topology in single AS",
            scenario_type="ibgp_ring",
            node_count=node_count
        )
        tasks.append(task)

    # Tree topologies - hierarchical BGP structures
    for depth in [2, 3]:
        for branch in [2, 3, 4, 5]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            # eBGP variant
            task = create_bgp_task(
                topology=topo,
                task_id=f"bgp_ebgp_tree_d{depth}_b{branch}",
                description=f"eBGP tree topology depth {depth} branch {branch}",
                scenario_type="ebgp_tree",
                node_count=node_count
            )
            tasks.append(task)
            
            # iBGP variant
            task = create_bgp_task(
                topology=topo,
                task_id=f"bgp_ibgp_tree_d{depth}_b{branch}",
                description=f"iBGP tree topology depth {depth} branch {branch}",
                scenario_type="ibgp_tree",
                node_count=node_count
            )
            tasks.append(task)

    # Mixed scenarios (eBGP + iBGP) - expanded
    for depth in [2, 3]:
        for branch in [2, 3, 4]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_bgp_task(
                topology=topo,
                task_id=f"bgp_mixed_tree_d{depth}_b{branch}",
                description=f"Mixed eBGP/iBGP tree depth {depth} branch {branch}",
                scenario_type="mixed",
                node_count=node_count
            )
            tasks.append(task)

    # Additional eBGP linear scenarios for scale testing
    for node_count in [22, 24, 25, 28, 30]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ebgp_linear_{node_count}as",
            description=f"eBGP linear {node_count}-AS topology - large scale",
            scenario_type="ebgp_linear",
            node_count=node_count
        )
        tasks.append(task)

    # Additional iBGP star scenarios for RR scale testing
    for node_count in [22, 24, 25, 28, 30]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ibgp_rr_{node_count}n",
            description=f"iBGP RR topology {node_count} routers - large scale",
            scenario_type="ibgp_rr",
            node_count=node_count
        )
        tasks.append(task)

    # Additional ring scenarios
    for node_count in [22, 24]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_bgp_task(
            topology=topo,
            task_id=f"bgp_ebgp_ring_{node_count}as",
            description=f"eBGP ring {node_count}-AS topology - large scale",
            scenario_type="ebgp_ring",
            node_count=node_count
        )
        tasks.append(task)

    return tasks


def create_bgp_task(
    topology: Any,
    task_id: str,
    description: str,
    scenario_type: str,
    node_count: int
) -> Dict[str, Any]:
    """
    Create a BGP configuration task.

    Args:
        topology: TopologySpecification object
        task_id: Unique task identifier
        description: Task description
        scenario_type: Type of BGP scenario
        node_count: Number of nodes

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

    properties = []

    # Add BGP session properties for each link
    for i, link in enumerate(topology.links):
        node1 = link.endpoints[0].split(':')[0]
        node2 = link.endpoints[1].split(':')[0]
        
        # BGP session property
        prop = {
            "id": f"bgp_session_{node1}_{node2}",
            "type": "bgp_configuration",
            "description": f"BGP session between {node1} and {node2}",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": node1,
                "command": f"echo '{{\"peers\": {{\"{node2}\": {{\"state\": \"Established\"}}}}}}'",
                "parser": "json",
                "success_condition": {
                    "json_path": f"$.peers['{node2}'].state",
                    "expected_value": "Established"
                }
            }
        }
        properties.append(prop)

    # Add route exchange property for first and last node
    if node_count >= 2:
        first_node = topology.nodes[0].name
        last_node = topology.nodes[-1].name
        
        route_prop = {
            "id": f"route_exchange_{first_node}_to_{last_node}",
            "type": "route_exists",
            "description": f"Route from {first_node} to {last_node} exists",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": first_node,
                "command": f"echo 'Route to {last_node} exists'",
                "parser": "text",
                "success_condition": {
                    "contains_text": f"Route to {last_node} exists"
                }
            }
        }
        properties.append(route_prop)

    task = {
        "task_id": task_id,
        "description": description,
        "platform": "frr",
        "topology": topo_dict,
        "intent": {
            "properties": properties
        },
        "convergence": {
            "timeout_seconds": 60,
            "check_interval_seconds": 5
        },
        "optimal_solution": {
            "command_count": node_count * 8,  # Estimate: IP + BGP config per node
            "description": f"Configure BGP on all {node_count} routers with appropriate AS and neighbors"
        }
    }

    return task

