"""
Topology Generator for creating network topologies.

Generates various graph patterns (linear, star, ring, mesh, tree) for
benchmark tasks.
"""
import sys
from pathlib import Path
from typing import List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.models.task import (
    TopologySpecification,
    Node,
    Link,
    NodeType,
    Platform,
)
from benchmark.platforms import get_platform_image


class TopologyGenerator:
    """Generate network topologies based on graph patterns."""

    def __init__(self, base_network: str = "10.0.0.0/8", default_platform: str = "frr"):
        """
        Initialize TopologyGenerator.

        Args:
            base_network: Base network for IP allocation
            default_platform: Default platform for nodes
        """
        self.base_network = base_network
        self.default_platform = default_platform
        self.ip_counter = 1

    def allocate_ip(self, subnet_offset: int = 0) -> str:
        """
        Allocate a unique IP address.

        Args:
            subnet_offset: Offset for subnet

        Returns:
            IP address string
        """
        # Simple IP allocation: 10.0.{subnet}.{host}
        host = self.ip_counter
        self.ip_counter += 1
        return f"10.0.{subnet_offset}.{host}"

    def _create_node(self, node_id: int) -> Node:
        """
        Create a router node.

        Args:
            node_id: Node number (1-indexed)

        Returns:
            Node object
        """
        return Node(
            name=f"R{node_id}",
            type=NodeType.ROUTER,
            image=get_platform_image(self.default_platform),
            platform=self.default_platform,
        )

    def _translate_interface(self, interface: str) -> str:
        """
        Translate interface name based on platform.
        
        Args:
            interface: Interface name in standard format (eth1, eth2, etc.)
            
        Returns:
            Platform-specific interface name
        """
        if self.default_platform == "nokia_srl":
            # Nokia requires ethernet-L/P format (e.g., eth1 -> ethernet-1/1)
            if interface.startswith("eth"):
                num = interface[3:]
                return f"ethernet-1/{num}"
        # FRR, VyOS, and linux use ethN format as-is
        return interface

    def _create_link(self, node1: str, interface1: str, node2: str, interface2: str) -> Link:
        """
        Create a link between two nodes.

        Args:
            node1: First node name
            interface1: First node interface
            node2: Second node name
            interface2: Second node interface

        Returns:
            Link object
        """
        # Translate interfaces based on platform
        intf1 = self._translate_interface(interface1)
        intf2 = self._translate_interface(interface2)
        return Link(endpoints=[f"{node1}:{intf1}", f"{node2}:{intf2}"])

    def generate_linear(self, node_count: int) -> TopologySpecification:
        """
        Generate a linear (chain) topology.

        Args:
            node_count: Number of nodes

        Returns:
            TopologySpecification with linear topology
        """
        nodes = [self._create_node(i) for i in range(1, node_count + 1)]
        links = []

        # Create sequential links: R1-R2, R2-R3, etc.
        for i in range(1, node_count):
            # Determine interface numbers
            # In a linear topology:
            # - R1 uses eth1 to connect to R2
            # - R2 uses eth1 (to R1) and eth2 (to R3)
            # - R3 uses eth1 (to R2) and eth2 (to R4)
            # - etc.
            if i == 1:
                # First link: R1:eth1 - R2:eth1
                intf1 = "eth1"
                intf2 = "eth1"
            else:
                # Subsequent links: R{i}:eth2 - R{i+1}:eth1
                intf1 = "eth2"
                intf2 = "eth1"

            link = self._create_link(f"R{i}", intf1, f"R{i+1}", intf2)
            links.append(link)

        return TopologySpecification(nodes=nodes, links=links)

    def generate_star(self, node_count: int) -> TopologySpecification:
        """
        Generate a star topology with R1 as hub.

        Args:
            node_count: Total number of nodes (hub + spokes)

        Returns:
            TopologySpecification with star topology
        """
        nodes = [self._create_node(i) for i in range(1, node_count + 1)]
        links = []

        # R1 is the hub, connect all other nodes to R1
        for i in range(2, node_count + 1):
            # Hub uses eth{i-1}, spoke uses eth1
            hub_intf = f"eth{i-1}"
            spoke_intf = "eth1"
            link = self._create_link("R1", hub_intf, f"R{i}", spoke_intf)
            links.append(link)

        return TopologySpecification(nodes=nodes, links=links)

    def generate_ring(self, node_count: int) -> TopologySpecification:
        """
        Generate a ring topology.

        Args:
            node_count: Number of nodes

        Returns:
            TopologySpecification with ring topology
        """
        nodes = [self._create_node(i) for i in range(1, node_count + 1)]
        links = []

        # Create sequential links
        for i in range(1, node_count + 1):
            if i < node_count:
                # Normal sequential links
                link = self._create_link(f"R{i}", "eth1" if i == 1 else "eth2", f"R{i+1}", "eth1")
            else:
                # Close the ring: last node back to first
                link = self._create_link(f"R{node_count}", "eth2", "R1", "eth2")
            links.append(link)

        return TopologySpecification(nodes=nodes, links=links)

    def generate_mesh(self, node_count: int) -> TopologySpecification:
        """
        Generate a full mesh topology.

        Args:
            node_count: Number of nodes

        Returns:
            TopologySpecification with mesh topology
        """
        nodes = [self._create_node(i) for i in range(1, node_count + 1)]
        links = []

        interface_counters = {i: 1 for i in range(1, node_count + 1)}

        # Connect every node to every other node
        for i in range(1, node_count + 1):
            for j in range(i + 1, node_count + 1):
                intf_i = f"eth{interface_counters[i]}"
                intf_j = f"eth{interface_counters[j]}"
                interface_counters[i] += 1
                interface_counters[j] += 1

                link = self._create_link(f"R{i}", intf_i, f"R{j}", intf_j)
                links.append(link)

        return TopologySpecification(nodes=nodes, links=links)

    def generate_tree(self, depth: int, branching_factor: int) -> TopologySpecification:
        """
        Generate a tree topology.

        Args:
            depth: Depth of the tree
            branching_factor: Number of children per node

        Returns:
            TopologySpecification with tree topology
        """
        nodes = []
        links = []
        node_id = 1

        # Track interface counters for each node's downlinks (to children)
        # eth1 is reserved for uplink (to parent), eth2+ for downlinks
        parent_downlink_counter = {}  # parent_id -> next downlink interface

        # Generate nodes level by level
        current_level = [node_id]
        nodes.append(self._create_node(node_id))
        parent_downlink_counter[node_id] = 1  # Root node starts at eth1 (no uplink)
        node_id += 1

        for level in range(depth):
            next_level = []
            for parent_id in current_level:
                for child_num in range(branching_factor):
                    child_id = node_id
                    nodes.append(self._create_node(child_id))
                    parent_downlink_counter[child_id] = 2  # Children start downlinks at eth2 (eth1 is uplink)

                    # Create link between parent and child
                    # Parent uses its next available downlink interface
                    parent_intf = f"eth{parent_downlink_counter[parent_id]}"
                    parent_downlink_counter[parent_id] += 1
                    # Child uses eth1 for uplink to parent
                    child_intf = "eth1"
                    link = self._create_link(f"R{parent_id}", parent_intf, f"R{child_id}", child_intf)
                    links.append(link)

                    next_level.append(child_id)
                    node_id += 1

            current_level = next_level

        return TopologySpecification(nodes=nodes, links=links)

    def reset_ip_counter(self) -> None:
        """Reset IP counter for new topology."""
        self.ip_counter = 1

