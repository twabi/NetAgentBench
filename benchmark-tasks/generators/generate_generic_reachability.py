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
    
    Uses simple Linux IP commands instead of FRR.
    """
    tasks = []
    
    # Linear topologies - simpler sizes for testing
    for node_count in [2, 3, 4, 5]:
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
            "timeout_seconds": 10,  # Linux is faster, less convergence needed
            "check_interval_seconds": 2
        },
        "optimal_solution": {
            "command_count": node_count * 2,
            "description": f"Configure IP addresses and routes on {node_count} Linux nodes"
        }
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
