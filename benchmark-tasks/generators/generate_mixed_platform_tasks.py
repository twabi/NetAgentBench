"""
Generate Mixed-Platform task variations.

Creates tasks where nodes use different network platforms (FRR, Nokia SRL, 
Nokia EOS, Nokia) within the same topology.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from topology_generator import TopologyGenerator


# Platform configurations with their container images
# Only FRR and Nokia SR Linux are used - they are the only free containerlab-compatible routers
PLATFORMS = {
    "frr": {
        "image": "frrouting/frr:latest",
        "display": "FRR"
    },
    "nokia_srl": {
        "image": "ghcr.io/nokia/srlinux:latest",
        "display": "Nokia SRL"
    }
}


def generate_mixed_platform_tasks() -> List[Dict[str, Any]]:
    """
    Generate all mixed-platform task variations.
    
    Target: 100+ unique tasks with different platform combinations.

    Returns:
        List of task dictionaries
    """
    generator = TopologyGenerator()
    tasks = []

    # Two-platform combinations: FRR + Nokia
    for node_count in [2, 3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_frr_nokia_linear_{node_count}n",
            platforms=["frr", "nokia_srl"],
            description=f"Linear {node_count}-node: FRR and Nokia SRL mixed topology"
        )
        tasks.append(task)

    # Two-platform combinations: FRR + Nokia
    for node_count in [2, 3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_frr_nokia_linear_{node_count}n",
            platforms=["frr", "nokia_srl"],
            description=f"Linear {node_count}-node: FRR and Nokia mixed topology"
        )
        tasks.append(task)

    # Two-platform combinations: FRR + Nokia
    for node_count in [2, 3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_frr_nokia_linear_{node_count}n",
            platforms=["frr", "nokia_srl"],
            description=f"Linear {node_count}-node: FRR and Nokia mixed topology"
        )
        tasks.append(task)

    # Two-platform combinations: Nokia + Nokia
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_nokia_nokia_linear_{node_count}n",
            platforms=["nokia_srl", "nokia_srl"],
            description=f"Linear {node_count}-node: Nokia SRL and Nokia mixed"
        )
        tasks.append(task)

    # Three-platform combinations
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_3plat_linear_{node_count}n",
            platforms=["frr", "nokia_srl", "nokia_srl"],
            description=f"Linear {node_count}-node: FRR, Nokia, Nokia mixed topology"
        )
        tasks.append(task)

    # Four-platform combinations
    for node_count in [4, 5, 6, 8]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_4plat_linear_{node_count}n",
            platforms=["frr", "nokia_srl", "nokia_srl", "nokia_srl"],
            description=f"Linear {node_count}-node: All four platforms mixed"
        )
        tasks.append(task)

    # Star topology with mixed platforms
    for node_count in [3, 4, 5, 6, 8]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_frr_nokia_star_{node_count}n",
            platforms=["frr", "nokia_srl"],
            hub_platform="frr",
            description=f"Star {node_count}-node: FRR hub, Nokia spokes"
        )
        tasks.append(task)

    # Star with Nokia hub
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_nokia_hub_star_{node_count}n",
            platforms=["nokia_srl", "frr"],
            hub_platform="nokia_srl",
            description=f"Star {node_count}-node: Nokia hub, FRR spokes"
        )
        tasks.append(task)

    # Ring topology mixed
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_ring_{node_count}n",
            platforms=["frr", "nokia_srl", "nokia_srl"],
            description=f"Ring {node_count}-node: Mixed FRR, Nokia, Nokia"
        )
        tasks.append(task)

    # Tree topology mixed
    for depth in [2, 3]:
        for branch in [2, 3]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_mixed_platform_task(
                topology=topo,
                task_id=f"mixed_tree_d{depth}_b{branch}",
                platforms=["frr", "nokia_srl"],
                description=f"Tree d{depth}b{branch} ({node_count} nodes): Mixed platforms"
            )
            tasks.append(task)

    # Mesh topology mixed
    for node_count in [3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_mesh_{node_count}n",
            platforms=["frr", "nokia_srl"],
            description=f"Mesh {node_count}-node: FRR and Nokia mixed"
        )
        tasks.append(task)

    # BGP-focused mixed platform (eBGP between different vendors)
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_ebgp_{node_count}n",
            platforms=["frr", "nokia_srl"],
            property_type="bgp_configuration",
            description=f"Linear {node_count}-node: eBGP between FRR and Nokia"
        )
        tasks.append(task)

    # OSPF-focused mixed platform
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_ospf_{node_count}n",
            platforms=["frr", "nokia_srl"],
            property_type="ospf_configuration",
            description=f"Linear {node_count}-node: OSPF between FRR and Nokia"
        )
        tasks.append(task)

    # Nokia-Nokia combinations
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_nokia_nokia_{node_count}n",
            platforms=["nokia_srl", "nokia_srl"],
            description=f"Linear {node_count}-node: Nokia and Nokia mixed"
        )
        tasks.append(task)

    # Nokia-Nokia combinations
    for node_count in [2, 3, 4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_nokia_nokia_{node_count}n",
            platforms=["nokia_srl", "nokia_srl"],
            description=f"Linear {node_count}-node: Nokia and Nokia mixed"
        )
        tasks.append(task)

    # Star with Nokia hub
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_nokia_hub_star_{node_count}n",
            platforms=["nokia_srl", "frr"],
            hub_platform="nokia_srl",
            description=f"Star {node_count}-node: Nokia hub, FRR spokes"
        )
        tasks.append(task)

    # Star with Nokia hub
    for node_count in [3, 4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_nokia_hub_star_{node_count}n",
            platforms=["nokia_srl", "nokia_srl"],
            hub_platform="nokia_srl",
            description=f"Star {node_count}-node: Nokia hub, Nokia spokes"
        )
        tasks.append(task)

    # Ring with 4 platforms
    for node_count in [4, 5, 6, 8]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_4plat_ring_{node_count}n",
            platforms=["frr", "nokia_srl", "nokia_srl", "nokia_srl"],
            description=f"Ring {node_count}-node: All four platforms"
        )
        tasks.append(task)

    # BGP with Nokia
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_ebgp_nokia_{node_count}n",
            platforms=["nokia_srl", "frr"],
            property_type="bgp_configuration",
            description=f"Linear {node_count}-node: eBGP between Nokia and FRR"
        )
        tasks.append(task)

    # OSPF with Nokia
    for node_count in [2, 3, 4]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_ospf_nokia_{node_count}n",
            platforms=["nokia_srl", "frr"],
            property_type="ospf_configuration",
            description=f"Linear {node_count}-node: OSPF between Nokia and FRR"
        )
        tasks.append(task)

    # Mesh with 4 platforms
    for node_count in [4, 5]:
        generator.reset_ip_counter()
        topo = generator.generate_mesh(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_4plat_mesh_{node_count}n",
            platforms=["frr", "nokia_srl", "nokia_srl", "nokia_srl"],
            description=f"Mesh {node_count}-node: All four platforms"
        )
        tasks.append(task)

    # Tree with Nokia root
    for depth in [2, 3]:
        for branch in [2, 3]:
            generator.reset_ip_counter()
            topo = generator.generate_tree(depth=depth, branching_factor=branch)
            node_count = len(topo.nodes)
            
            task = create_mixed_platform_task(
                topology=topo,
                task_id=f"mixed_nokia_tree_d{depth}_b{branch}",
                platforms=["nokia_srl", "nokia_srl"],
                hub_platform="nokia_srl",
                description=f"Tree d{depth}b{branch} ({node_count} nodes): Nokia root"
            )
            tasks.append(task)

    # Additional Nokia-FRR stars
    for node_count in [7, 8, 10]:
        generator.reset_ip_counter()
        topo = generator.generate_star(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_nokia_frr_star_{node_count}n",
            platforms=["nokia_srl", "frr"],
            hub_platform="nokia_srl",
            description=f"Star {node_count}-node: Nokia hub with FRR spokes"
        )
        tasks.append(task)

    # Larger linear topologies
    for node_count in [7, 8, 9, 10]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_4plat_linear_{node_count}n_large",
            platforms=["frr", "nokia_srl", "nokia_srl", "nokia_srl"],
            description=f"Linear {node_count}-node: All platforms, larger scale"
        )
        tasks.append(task)

    # Ring with vendor alternation
    for node_count in [4, 6, 8, 10]:
        generator.reset_ip_counter()
        topo = generator.generate_ring(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_alternating_ring_{node_count}n",
            platforms=["frr", "nokia_srl"],
            description=f"Ring {node_count}-node: FRR-Nokia alternating"
        )
        tasks.append(task)

    # BGP with all platforms
    for node_count in [4, 5, 6]:
        generator.reset_ip_counter()
        topo = generator.generate_linear(node_count)
        
        task = create_mixed_platform_task(
            topology=topo,
            task_id=f"mixed_ebgp_4plat_{node_count}n",
            platforms=["frr", "nokia_srl", "nokia_srl", "nokia_srl"],
            property_type="bgp_configuration",
            description=f"Linear {node_count}-node: eBGP across all 4 platforms"
        )
        tasks.append(task)

    return tasks


def create_mixed_platform_task(
    topology: Any,
    task_id: str,
    platforms: List[str],
    description: str,
    hub_platform: str = None,
    property_type: str = "reachability"
) -> Dict[str, Any]:
    """
    Create a mixed-platform task.

    Args:
        topology: TopologySpecification object
        task_id: Unique task identifier
        platforms: List of platform names to use
        description: Task description
        hub_platform: Platform for hub node in star topology
        property_type: Primary property type for this task

    Returns:
        Task dictionary
    """
    # Assign platforms to nodes in round-robin fashion
    nodes_list = []
    node_platforms = {}  # name -> platform mapping
    
    for i, node in enumerate(topology.nodes):
        if hub_platform and i == 0:
            # First node gets hub platform for star topologies
            platform = hub_platform
        else:
            # Round-robin assignment
            platform = platforms[i % len(platforms)]
        
        node_platforms[node.name] = platform
        nodes_list.append({
            "name": node.name,
            "type": node.type,
            "image": PLATFORMS[platform]["image"],
            "platform": platform,
        })

    # Translate interface names based on platform
    def translate_interface(node_name: str, interface: str) -> str:
        """Translate interface name based on node's platform."""
        platform = node_platforms.get(node_name, "frr")
        
        if platform == "nokia_srl":
            # Nokia requires ethernet-L/P format (e.g., eth1 -> ethernet-1/1)
            if interface.startswith("eth"):
                num = interface[3:]
                return f"ethernet-1/{num}"
            return interface
        else:
            # FRR, Nokia, and linux use ethN format as-is
            return interface

    # Process links with translated interface names
    links_list = []
    for link in topology.links:
        endpoints = link.endpoints
        if len(endpoints) == 2:
            # Parse node:interface format
            node1, intf1 = endpoints[0].split(":")
            node2, intf2 = endpoints[1].split(":")
            
            # Translate interfaces based on each node's platform
            new_intf1 = translate_interface(node1, intf1)
            new_intf2 = translate_interface(node2, intf2)
            
            links_list.append({
                "endpoints": [f"{node1}:{new_intf1}", f"{node2}:{new_intf2}"]
            })

    topo_dict = {
        "nodes": nodes_list,
        "links": links_list,
        "interfaces": []
    }

    # Determine target node and property
    target_node = topology.nodes[0].name
    
    properties = []
    
    # Primary property: Reachability between different platforms
    reach_prop = {
        "id": f"mixed_platform_connectivity",
        "type": property_type,
        "description": f"Connectivity verified between mixed platforms",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": target_node,
            "command": "ping -c 3 192.168.1.2",
            "parser": "text",
            "success_condition": {
                "contains_text": "3 packets transmitted"
            }
        }
    }
    properties.append(reach_prop)

    # Secondary property: Platform interoperability
    interop_prop = {
        "id": f"platform_interop",
        "type": "interface_up",
        "description": f"Interfaces up across platform boundary",
        "evaluation": {
            "method": "exec_and_parse",
            "target_node": target_node,
            "command": "ip link show",
            "parser": "text",
            "success_condition": {
                "contains_text": "state UP"
            }
        }
    }
    properties.append(interop_prop)

    # Estimate command count (more for mixed platforms)
    node_count = len(topology.nodes)
    cmd_count = node_count * 4  # More commands for multi-vendor setup

    # Collect unique platforms used
    used_platforms = list(set(n["platform"] for n in nodes_list))

    task = {
        "task_id": task_id,
        "description": description,
        "platform": "frr",  # Primary platform (for backwards compat)
        "mixed_platforms": used_platforms,  # New field for mixed
        "topology": topo_dict,
        "intent": {
            "properties": properties
        },
        "convergence": {
            "timeout_seconds": 45,  # Longer for multi-vendor
            "check_interval_seconds": 3
        },
        "optimal_solution": {
            "command_count": cmd_count,
            "description": f"Configure connectivity across {len(used_platforms)} platforms"
        }
    }

    return task
