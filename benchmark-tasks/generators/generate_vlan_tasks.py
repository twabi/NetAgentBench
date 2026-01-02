"""
Generate VLAN configuration task variations.

Creates tasks that test VLAN creation, trunk configuration, and access port setup.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator


def generate_vlan_tasks(platform: str = "frr") -> List[Dict[str, Any]]:
    """
    Generate all VLAN configuration task variations.
    
    Target: 100+ unique tasks with diverse VLAN scenarios.

    Returns:
        List of task dictionaries
    """
    generator = TopologyGenerator(default_platform=platform)
    tasks = []

    # Simple VLAN creation tasks (2-node topologies) - expanded VLAN IDs
    for vlan_id in [10, 20, 30, 50, 100, 200, 300, 400, 500, 1000, 2000, 3000]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(2)
        
        task = create_vlan_task(
            topology=topo,
            task_id=f"vlan_create_vlan{vlan_id}",
            description=f"Configure VLAN {vlan_id} on 2 switches",
            vlan_config={"id": vlan_id, "name": f"VLAN_{vlan_id}"},
            scenario="creation",
            platform=platform
        )
        tasks.append(task)

    # Access port configuration - expanded node counts and VLANs
    for node_count in [2, 3, 4, 5, 6, 8, 10]:
        for vlan_id in [10, 20, 100, 200]:
            generator.reset_ip_counter()
            topo = generator.generate_star(node_count)
            
            task = create_vlan_task(
                topology=topo,
                task_id=f"vlan_access_{node_count}n_vlan{vlan_id}",
                description=f"Configure Access ports for VLAN {vlan_id}",
                vlan_config={"id": vlan_id, "mode": "access"},
                scenario="access",
                platform=platform
            )
            tasks.append(task)

    # Trunk configuration - expanded
    for node_count in [2, 3, 4, 5, 6, 8, 10, 12]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_vlan_task(
            topology=topo,
            task_id=f"vlan_trunk_linear_{node_count}n",
            description=f"Configure Trunk with VLAN 10, 20, 30 allowed",
            vlan_config={"id": 10, "name": "DATA", "mode": "trunk", "allowed_vlans": [10, 20, 30]},
            scenario="trunk",
            platform=platform
        )
        tasks.append(task)

    # Multiple VLANs on same topology - expanded
    for node_count in [2, 3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_vlan_task(
            topology=topo,
            task_id=f"vlan_multi_{node_count}n",
            description=f"Linear {node_count}-node: Create multiple VLANs (10,20,30,40)",
            vlan_config={"id": 10, "name": "MULTI", "multi_vlan_list": [10, 20, 30, 40]},
            scenario="multi_vlan",
            platform=platform
        )
        tasks.append(task)

    # Native VLAN configuration - expanded
    for node_count in [2, 3, 4, 5, 6]:
        for native_id in [1, 99, 999]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_vlan_task(
                topology=topo,
                task_id=f"vlan_native_{node_count}n_vlan{native_id}",
                description=f"Linear {node_count}-node: Configure native VLAN {native_id} on trunks",
                vlan_config={"id": native_id, "name": "NATIVE", "mode": "trunk", "native_vlan": native_id},
                scenario="native_vlan",
                platform=platform
            )
            tasks.append(task)

    # Inter-VLAN routing setup (SVI) - expanded
    for node_count in [2, 3, 4]:
        for vlan_id in [10, 20, 100, 200]:
            generator.reset_ip_counter()
            topo = generator.generate_linear(node_count)
            
            task = create_vlan_task(
                topology=topo,
                task_id=f"vlan_svi_{node_count}n_vlan{vlan_id}",
                description=f"Linear {node_count}-node: Create VLAN {vlan_id} SVI with IP",
                vlan_config={"id": vlan_id, "name": f"SVI{vlan_id}", "svi_ip": f"192.168.{vlan_id}.1/24"},
                scenario="svi",
                platform=platform
            )
            tasks.append(task)

    # Star topology with hub as trunk, spokes as access - expanded
    for node_count in [3, 4, 5, 6, 8, 10, 12]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_vlan_task(
            topology=topo,
            task_id=f"vlan_hub_trunk_{node_count}n",
            description=f"Star {node_count}-node: Hub has trunks, spokes have access ports",
            vlan_config={"id": 10, "name": "HUBTRUNK"},
            scenario="hub_trunk",
            platform=platform
        )
        tasks.append(task)

    # Ring topology VLAN propagation - expanded
    for node_count in [3, 4, 5, 6, 8, 10]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_vlan_task(
            topology=topo,
            task_id=f"vlan_ring_{node_count}n",
            description=f"Ring {node_count}-node: Configure VLAN 100 across ring with trunks",
            vlan_config={"id": 100, "name": "RING", "mode": "trunk"},
            scenario="trunk",
            platform=platform
        )
        tasks.append(task)

    # Tree topology VLANs
    for depth in [2, 3]:
        for branch in [2, 3]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_vlan_task(
                topology=topo,
                task_id=f"vlan_tree_d{depth}_b{branch}",
                description=f"Tree d{depth}b{branch} ({node_count} nodes): VLAN propagation",
                vlan_config={"id": 50, "name": "TREE", "mode": "trunk"},
                scenario="trunk",
                platform=platform
            )
            tasks.append(task)

    # Voice + Data VLAN separation
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_vlan_task(
            topology=topo,
            task_id=f"vlan_voice_data_{node_count}n",
            description=f"Linear {node_count}-node: Voice (20) and Data (10) VLAN separation",
            vlan_config={"id": 10, "name": "DATA", "multi_vlan_list": [10, 20]},
            scenario="voice_data",
            platform=platform
        )
        tasks.append(task)

    return tasks


def create_vlan_task(
    topology: Any,
    task_id: str,
    description: str,
    vlan_config: Dict[str, Any],
    scenario: str,
    platform: str = "frr"
) -> Dict[str, Any]:
    """
    Create a VLAN configuration task.

    Args:
        topology: TopologySpecification object
        task_id: Unique task identifier
        description: Task description
        svi_ip: IP address for SVI
        hub_trunk: If True, hub has trunk, spokes have access

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

    # Extract config
    vlan_id = vlan_config.get("id")
    mode = vlan_config.get("mode")
    trunk_ports = mode == "trunk"
    access_ports = mode == "access"
    allowed_vlans = vlan_config.get("allowed_vlans")
    vlan_list = vlan_config.get("multi_vlan_list", [])
    multi_vlan = bool(vlan_list)
    native_vlan = vlan_config.get("native_vlan")
    svi_ip = vlan_config.get("svi_ip")
    svi_config = bool(svi_ip)
    
    properties = []
    
    # Primary property: VLAN exists
    vlan_prop = {
        "id": f"vlan_{vlan_id}_exists",
        "type": "vlan_configuration",
        "description": f"VLAN {vlan_id} exists on all nodes",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": topology.nodes[0].name,
            "command": "vtysh -c 'show vlan brief'",
            "parser": "text",
            "success_condition": {
                "contains_text": str(vlan_id)
            }
        }
    }
    properties.append(vlan_prop)

    # Trunk verification
    if trunk_ports:
        trunk_prop = {
            "id": f"trunk_configured",
            "type": "trunk_configuration",
            "description": "Trunk ports configured correctly",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": topology.nodes[0].name,
                "command": "vtysh -c 'show interface trunk'",
                "parser": "text",
                "success_condition": {
                    "contains_text": "trunk"
                }
            }
        }
        properties.append(trunk_prop)

    # SVI verification
    if svi_config and svi_ip:
        svi_prop = {
            "id": f"svi_vlan{vlan_id}",
            "type": "svi_configuration",
            "description": f"SVI for VLAN {vlan_id} has correct IP",
            "evaluation": {
                "method": "exec_and_parse",
                "target_node": topology.nodes[0].name,
                "command": f"vtysh -c 'show ip interface vlan{vlan_id}'",
                "parser": "text",
                "success_condition": {
                    "contains_text": svi_ip.split('/')[0]
                }
            }
        }
        properties.append(svi_prop)

    # Estimate command count
    node_count = len(topology.nodes)
    if multi_vlan and vlan_list:
        cmd_count = node_count * len(vlan_list) * 2
    elif trunk_ports:
        cmd_count = node_count * 4
    elif svi_config:
        cmd_count = node_count * 3
    else:
        cmd_count = node_count * 2

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
            "description": f"Configure VLANs on {node_count} nodes"
        }
    }

    return task
