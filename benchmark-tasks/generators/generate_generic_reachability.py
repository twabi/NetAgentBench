"""
Generate generic reachability tasks using Alpine Linux containers.

Creates simple reachability tasks that use basic Linux IP commands
instead of FRR/vtysh for easier LLM configuration generation.
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def generate_generic_reachability_tasks() -> List[Dict[str, Any]]:
    """
    Generate reachability tasks for generic (Alpine Linux) platform.
    
    Target: 100+ unique tasks with diverse topologies.
    Uses simple Linux IP commands instead of FRR.
    """
    tasks = []
    
    # Linear topologies - expanded range
    for node_count in [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20]:
        # Forward direction: R1 to Rn
        task = create_linear_reachability_task(
            node_count=node_count,
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.{node_count}.1",
        )
        tasks.append(task)
        
        # Reverse direction for 3+ nodes
        if node_count >= 3:
            task = create_linear_reachability_task(
                node_count=node_count,
                source=f"R{node_count}",
                destination="R1",
                dest_ip="192.168.1.1",
            )
            tasks.append(task)
        
        # Middle-to-end for 5+ nodes
        if node_count >= 5:
            mid = node_count // 2
            task = create_linear_reachability_task(
                node_count=node_count,
                source=f"R{mid}",
                destination=f"R{node_count}",
                dest_ip=f"192.168.{node_count}.1",
            )
            tasks.append(task)

    # Star topologies
    for node_count in [3, 4, 5, 6, 7, 8, 10, 12, 15]:
        # Hub to spoke
        task = create_star_reachability_task(
            node_count=node_count,
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.{node_count}.1",
        )
        tasks.append(task)
        
        # Spoke to spoke (through hub) for 4+ nodes
        if node_count >= 4:
            task = create_star_reachability_task(
                node_count=node_count,
                source="R2",
                destination="R3",
                dest_ip="192.168.3.1",
            )
            tasks.append(task)

    # Ring topologies
    for node_count in [3, 4, 5, 6, 8, 10, 12]:
        task = create_ring_reachability_task(
            node_count=node_count,
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.{node_count}.1",
        )
        tasks.append(task)
        
        # Opposite direction
        if node_count >= 4:
            mid = node_count // 2
            task = create_ring_reachability_task(
                node_count=node_count,
                source="R1",
                destination=f"R{mid}",
                dest_ip=f"192.168.{mid}.1",
            )
            tasks.append(task)

    # Mesh topologies (smaller sizes due to complexity)
    for node_count in [3, 4, 5, 6]:
        task = create_mesh_reachability_task(
            node_count=node_count,
            source="R1",
            destination=f"R{node_count}",
            dest_ip=f"192.168.{node_count}.1",
        )
        tasks.append(task)
        
        if node_count >= 4:
            task = create_mesh_reachability_task(
                node_count=node_count,
                source="R2",
                destination=f"R{node_count-1}",
                dest_ip=f"192.168.{node_count-1}.1",
            )
            tasks.append(task)

    # Tree topologies
    for depth in [2, 3]:
        for branch in [2, 3]:
            node_count = sum(branch**i for i in range(depth + 1))
            task = create_tree_reachability_task(
                depth=depth,
                branch=branch,
                source="R1",
                destination=f"R{node_count}",
                dest_ip=f"192.168.{node_count}.1",
            )
            tasks.append(task)
    
    return tasks


def create_linear_reachability_task(
    node_count: int,
    source: str,
    destination: str,
    dest_ip: str,
) -> Dict[str, Any]:
    """Create a linear reachability task with Alpine nodes."""
    
    # Create nodes
    nodes = []
    for i in range(1, node_count + 1):
        nodes.append({
            "name": f"R{i}",
            "type": "router",
            "image": "alpine:latest",
            "platform": "linux"
        })
    
    # Create links: R1:eth1 -- R2:eth1, R2:eth2 -- R3:eth1, etc.
    links = []
    for i in range(1, node_count):
        if i == 1:
            # First link: R1:eth1 - R2:eth1
            intf1 = "eth1"
            intf2 = "eth1"
        else:
            # Subsequent links: Ri:eth2 - Ri+1:eth1
            intf1 = "eth2"
            intf2 = "eth1"
        
        links.append({
            "endpoints": [f"R{i}:{intf1}", f"R{i+1}:{intf2}"]
        })
    
    task_id = f"reach_linux_{node_count}n_{source}_to_{destination}"
    
    # Property: ping test
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
    
    return {
        "task_id": task_id,
        "description": f"Linux {node_count}-node linear: {source} to {destination} reachability",
        "platform": "linux",
        "topology": {
            "nodes": nodes,
            "links": links,
            "interfaces": []
        },
        "intent": {
            "properties": [property_def]
        },
        "convergence": {
            "timeout_seconds": 10,
            "check_interval_seconds": 2
        },
        "optimal_solution": {
            "command_count": node_count * 2,
            "description": f"Configure IP addresses and routes on {node_count} Linux nodes"
        }
    }


def create_star_reachability_task(
    node_count: int,
    source: str,
    destination: str,
    dest_ip: str,
) -> Dict[str, Any]:
    """Create a star topology reachability task with Alpine nodes."""
    
    nodes = []
    for i in range(1, node_count + 1):
        nodes.append({
            "name": f"R{i}",
            "type": "router",
            "image": "alpine:latest",
            "platform": "linux"
        })
    
    # Star: R1 is hub, all others connect to R1
    links = []
    for i in range(2, node_count + 1):
        links.append({
            "endpoints": [f"R1:eth{i-1}", f"R{i}:eth1"]
        })
    
    task_id = f"reach_linux_star_{node_count}n_{source}_to_{destination}"
    
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
    
    return {
        "task_id": task_id,
        "description": f"Linux {node_count}-node star: {source} to {destination} reachability",
        "platform": "linux",
        "topology": {"nodes": nodes, "links": links, "interfaces": []},
        "intent": {"properties": [property_def]},
        "convergence": {"timeout_seconds": 10, "check_interval_seconds": 2},
        "optimal_solution": {"command_count": node_count * 2, "description": f"Configure star topology on {node_count} Linux nodes"}
    }


def create_ring_reachability_task(
    node_count: int,
    source: str,
    destination: str,
    dest_ip: str,
) -> Dict[str, Any]:
    """Create a ring topology reachability task with Alpine nodes."""
    
    nodes = []
    for i in range(1, node_count + 1):
        nodes.append({
            "name": f"R{i}",
            "type": "router",
            "image": "alpine:latest",
            "platform": "linux"
        })
    
    # Ring: each node connects to next, last connects back to first
    links = []
    for i in range(1, node_count + 1):
        if i < node_count:
            links.append({"endpoints": [f"R{i}:eth2", f"R{i+1}:eth1"]})
        else:
            links.append({"endpoints": [f"R{node_count}:eth2", "R1:eth1"]})
    
    task_id = f"reach_linux_ring_{node_count}n_{source}_to_{destination}"
    
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
    
    return {
        "task_id": task_id,
        "description": f"Linux {node_count}-node ring: {source} to {destination} reachability",
        "platform": "linux",
        "topology": {"nodes": nodes, "links": links, "interfaces": []},
        "intent": {"properties": [property_def]},
        "convergence": {"timeout_seconds": 10, "check_interval_seconds": 2},
        "optimal_solution": {"command_count": node_count * 3, "description": f"Configure ring topology on {node_count} Linux nodes"}
    }


def create_mesh_reachability_task(
    node_count: int,
    source: str,
    destination: str,
    dest_ip: str,
) -> Dict[str, Any]:
    """Create a full mesh topology reachability task with Alpine nodes."""
    
    nodes = []
    for i in range(1, node_count + 1):
        nodes.append({
            "name": f"R{i}",
            "type": "router",
            "image": "alpine:latest",
            "platform": "linux"
        })
    
    # Full mesh: every node connects to every other
    links = []
    interface_counters = {i: 1 for i in range(1, node_count + 1)}
    for i in range(1, node_count + 1):
        for j in range(i + 1, node_count + 1):
            links.append({
                "endpoints": [f"R{i}:eth{interface_counters[i]}", f"R{j}:eth{interface_counters[j]}"]
            })
            interface_counters[i] += 1
            interface_counters[j] += 1
    
    task_id = f"reach_linux_mesh_{node_count}n_{source}_to_{destination}"
    
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
    
    return {
        "task_id": task_id,
        "description": f"Linux {node_count}-node mesh: {source} to {destination} reachability",
        "platform": "linux",
        "topology": {"nodes": nodes, "links": links, "interfaces": []},
        "intent": {"properties": [property_def]},
        "convergence": {"timeout_seconds": 10, "check_interval_seconds": 2},
        "optimal_solution": {"command_count": node_count * 3, "description": f"Configure mesh topology on {node_count} Linux nodes"}
    }


def create_tree_reachability_task(
    depth: int,
    branch: int,
    source: str,
    destination: str,
    dest_ip: str,
) -> Dict[str, Any]:
    """Create a tree topology reachability task with Alpine nodes."""
    
    # Generate tree nodes level by level
    nodes = []
    links = []
    node_id = 1
    
    # Track interface counters for each node's downlinks (to children)
    # eth1 is reserved for uplink (to parent), eth2+ for downlinks
    parent_downlink_counter = {}
    
    current_level = [node_id]
    nodes.append({"name": f"R{node_id}", "type": "router", "image": "alpine:latest", "platform": "linux"})
    parent_downlink_counter[node_id] = 1  # Root starts at eth1 (no uplink)
    node_id += 1
    
    for level in range(depth):
        next_level = []
        for parent_id in current_level:
            for child_num in range(branch):
                child_id = node_id
                nodes.append({"name": f"R{child_id}", "type": "router", "image": "alpine:latest", "platform": "linux"})
                parent_downlink_counter[child_id] = 2  # Children start downlinks at eth2 (eth1 is uplink)
                
                # Parent uses its next available downlink interface
                parent_intf = f"eth{parent_downlink_counter[parent_id]}"
                parent_downlink_counter[parent_id] += 1
                # Child uses eth1 for uplink to parent
                links.append({"endpoints": [f"R{parent_id}:{parent_intf}", f"R{child_id}:eth1"]})
                next_level.append(child_id)
                node_id += 1
        current_level = next_level
    
    node_count = len(nodes)
    task_id = f"reach_linux_tree_d{depth}_b{branch}_{source}_to_{destination}"
    
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
    
    return {
        "task_id": task_id,
        "description": f"Linux tree depth={depth} branch={branch}: {source} to {destination} reachability",
        "platform": "linux",
        "topology": {"nodes": nodes, "links": links, "interfaces": []},
        "intent": {"properties": [property_def]},
        "convergence": {"timeout_seconds": 10, "check_interval_seconds": 2},
        "optimal_solution": {"command_count": node_count * 2, "description": f"Configure tree topology on {node_count} Linux nodes"}
    }


def main():
    """Generate and save generic reachability tasks."""
    output_dir = Path(__file__).parent.parent / "generic" / "reachability" / "tasks"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tasks = generate_generic_reachability_tasks()
    
    print(f"Generating {len(tasks)} generic reachability tasks...")
    
    for task in tasks:
        task_file = output_dir / f"{task['task_id']}.json"
        with open(task_file, 'w') as f:
            json.dump(task, f, indent=2)
        print(f"  Created: {task['task_id']}")
    
    print(f"\nSaved to: {output_dir}")
    print(f"Total tasks: {len(tasks)}")


if __name__ == "__main__":
    main()
