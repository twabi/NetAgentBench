"""
Generate reachability task variations.

Creates tasks that test network connectivity between nodes using various
topology patterns.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator
from benchmark.models.task import PropertyType


def generate_reachability_tasks() -> List[Dict[str, Any]]:
    """
    Generate all reachability task variations.
    
    Target: 100+ unique tasks with diverse topologies and test scenarios.

    Returns:
        List of task dictionaries (not yet validated as TaskDefinition)
    """
    generator = TopologyGenerator()
    tasks = []

    # Linear topologies - expanded range and multiple test pairs
    for node_count in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        # Test reachability from first to last node
        task = create_reachability_task(
            topology=topo,
            task_id=f"reachability_linear_{node_count}n_R1_to_R{node_count}",
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.{node_count}.{node_count}",
            description=f"Linear {node_count}-node topology: R1 to R{node_count} reachability"
        )
        tasks.append(task)
        
        # Add middle-to-end tests
        if node_count >= 5:
            mid = node_count // 2
            task = create_reachability_task(
                topology=topo,
                task_id=f"reachability_linear_{node_count}n_R{mid}_to_R{node_count}",
                source=f"R{mid}",
                destination=f"R{node_count}",
                dest_ip=f"192.168.{node_count}.{node_count}",
                description=f"Linear {node_count}-node topology: R{mid} to R{node_count} reachability"
            )
            tasks.append(task)
        
        # Add reverse direction for larger topologies
        if node_count >= 8:
            task = create_reachability_task(
                topology=topo,
                task_id=f"reachability_linear_{node_count}n_R{node_count}_to_R1",
                source=f"R{node_count}",
                destination="R1",
                dest_ip="192.168.1.1",
                description=f"Linear {node_count}-node topology: R{node_count} to R1 reachability (reverse)"
            )
            tasks.append(task)

    # Star topologies - expanded with more variations
    for node_count in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        # Test reachability from hub to spoke
        task = create_reachability_task(
            topology=topo,
            task_id=f"reachability_star_{node_count}n_R1_to_R{node_count}",
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.1.{node_count}",
            description=f"Star {node_count}-node topology: Hub R1 to spoke R{node_count} reachability"
        )
        tasks.append(task)
        
        # Test spoke to spoke (through hub)
        if node_count >= 4:
            task = create_reachability_task(
                topology=topo,
                task_id=f"reachability_star_{node_count}n_R2_to_R3",
                source="R2",
                destination="R3",
                dest_ip="192.168.2.3",
                description=f"Star {node_count}-node topology: Spoke R2 to spoke R3 reachability"
            )
            tasks.append(task)

    # Ring topologies - expanded range
    for node_count in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        # Test reachability from first to last (around the ring)
        task = create_reachability_task(
            topology=topo,
            task_id=f"reachability_ring_{node_count}n_R1_to_R{node_count}",
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.{node_count}.{node_count}",
            description=f"Ring {node_count}-node topology: R1 to R{node_count} reachability"
        )
        tasks.append(task)
        
        # Add diagonal test for larger rings
        if node_count >= 6:
            mid = node_count // 2
            task = create_reachability_task(
                topology=topo,
                task_id=f"reachability_ring_{node_count}n_R1_to_R{mid}",
                source="R1",
                destination=f"R{mid}",
                dest_ip=f"192.168.{mid}.{mid}",
                description=f"Ring {node_count}-node topology: R1 to R{mid} reachability (halfway)"
            )
            tasks.append(task)

    # Mesh topologies - expanded
    for node_count in [3, 4, 5, 6, 7]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        # Test reachability between any two nodes
        task = create_reachability_task(
            topology=topo,
            task_id=f"reachability_mesh_{node_count}n_R1_to_R{node_count}",
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.1.{node_count}",
            description=f"Mesh {node_count}-node topology: R1 to R{node_count} reachability"
        )
        tasks.append(task)
        
        # Add cross-mesh test
        if node_count >= 4:
            task = create_reachability_task(
                topology=topo,
                task_id=f"reachability_mesh_{node_count}n_R2_to_R{node_count-1}",
                source="R2",
                destination=f"R{node_count-1}",
                dest_ip=f"192.168.2.{node_count-1}",
                description=f"Mesh {node_count}-node topology: R2 to R{node_count-1} reachability"
            )
            tasks.append(task)

    # Tree topologies - hierarchical structures
    for depth in [2, 3]:
        for branch in [2, 3, 4]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_reachability_task(
                topology=topo,
                task_id=f"reachability_tree_d{depth}_b{branch}_R1_to_R{node_count}",
                source="R1",
                destination=f"R{node_count}",
                dest_ip=f"192.168.1.{node_count}",
                description=f"Tree depth {depth} branch {branch}: R1 to R{node_count} reachability"
            )
            tasks.append(task)

    return tasks


def create_reachability_task(
    topology: Any,
    task_id: str,
    source: str,
    destination: str,
    dest_ip: str,
    description: str
) -> Dict[str, Any]:
    """
    Create a reachability task.

    Args:
        topology: TopologySpecification object
        task_id: Unique task identifier
        source: Source node name
        destination: Destination node name
        dest_ip: Destination IP address
        description: Task description

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

    # Create reachability property
    property_def = {
        "id": f"reachability_{source}_to_{destination}",
        "type": "reachability",
        "description": f"{source} can reach {destination} via ping",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": source,
            "command": f"ping -c 3 {dest_ip}",
            "parser": "text",
            "success_condition": {
                "contains_text": "3 packets transmitted, 3 packets received"
            }
        }
    }

    task = {
        "task_id": task_id,
        "description": description,
        "platform": "frr",
        "topology": topo_dict,
        "intent": {
            "properties": [property_def]
        },
        "convergence": {
            "timeout_seconds": 30,
            "check_interval_seconds": 2
        },
        "optimal_solution": {
            "command_count": len(topology.nodes) * 2,  # IP config + interface up per node
            "description": f"Configure IP addresses and bring up interfaces on all {len(topology.nodes)} nodes"
        }
    }

    return task

