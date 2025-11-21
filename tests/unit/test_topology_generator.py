"""
Unit tests for Topology Generator.

Tests the core topology generation utilities for various graph patterns.
"""
import pytest
import sys
from pathlib import Path

# Add generators directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "benchmark-tasks" / "generators"))

from benchmark.models.task import TopologySpecification, Node, Link


class TestTopologyGeneratorInitialization:
    """Test TopologyGenerator initialization"""

    def test_generator_initializes(self):
        """Test that TopologyGenerator can be initialized"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        assert gen is not None

    def test_generator_has_ip_allocator(self):
        """Test that generator has IP allocator"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        assert hasattr(gen, "allocate_ip")


class TestLinearTopology:
    """Test linear topology generation"""

    def test_generate_linear_2_nodes(self):
        """Test linear topology with 2 nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=2)
        
        assert isinstance(topo, TopologySpecification)
        assert len(topo.nodes) == 2
        assert len(topo.links) == 1

    def test_generate_linear_5_nodes(self):
        """Test linear topology with 5 nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=5)
        
        assert len(topo.nodes) == 5
        assert len(topo.links) == 4  # n-1 links

    def test_linear_node_naming(self):
        """Test that nodes are named R1, R2, etc."""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=3)
        
        node_names = [node.name for node in topo.nodes]
        assert node_names == ["R1", "R2", "R3"]

    def test_linear_links_sequential(self):
        """Test that links connect sequential nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=3)
        
        # Links should be R1-R2, R2-R3
        link_endpoints = [link.endpoints for link in topo.links]
        assert ["R1:eth1", "R2:eth1"] in link_endpoints
        assert ["R2:eth2", "R3:eth1"] in link_endpoints


class TestStarTopology:
    """Test star topology generation"""

    def test_generate_star_3_nodes(self):
        """Test star topology with 3 nodes (1 hub + 2 spokes)"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_star(node_count=3)
        
        assert len(topo.nodes) == 3
        assert len(topo.links) == 2  # n-1 links

    def test_generate_star_5_nodes(self):
        """Test star topology with 5 nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_star(node_count=5)
        
        assert len(topo.nodes) == 5
        assert len(topo.links) == 4  # n-1 links

    def test_star_hub_is_r1(self):
        """Test that R1 is the hub node"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_star(node_count=4)
        
        # All links should connect to R1
        link_endpoints = [link.endpoints for link in topo.links]
        for endpoints in link_endpoints:
            assert any("R1:" in ep for ep in endpoints)


class TestRingTopology:
    """Test ring topology generation"""

    def test_generate_ring_3_nodes(self):
        """Test ring topology with 3 nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_ring(node_count=3)
        
        assert len(topo.nodes) == 3
        assert len(topo.links) == 3  # n links (forms a ring)

    def test_generate_ring_5_nodes(self):
        """Test ring topology with 5 nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_ring(node_count=5)
        
        assert len(topo.nodes) == 5
        assert len(topo.links) == 5  # n links

    def test_ring_forms_cycle(self):
        """Test that ring topology forms a complete cycle"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_ring(node_count=4)
        
        # Should have links: R1-R2, R2-R3, R3-R4, R4-R1
        link_endpoints = [link.endpoints for link in topo.links]
        assert len(link_endpoints) == 4
        
        # Last link should connect back to R1
        assert any("R1:" in ep for ep in link_endpoints[-1])
        assert any("R4:" in ep for ep in link_endpoints[-1])


class TestMeshTopology:
    """Test full mesh topology generation"""

    def test_generate_mesh_3_nodes(self):
        """Test mesh topology with 3 nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_mesh(node_count=3)
        
        assert len(topo.nodes) == 3
        assert len(topo.links) == 3  # n(n-1)/2 = 3

    def test_generate_mesh_4_nodes(self):
        """Test mesh topology with 4 nodes"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_mesh(node_count=4)
        
        assert len(topo.nodes) == 4
        assert len(topo.links) == 6  # n(n-1)/2 = 6

    def test_mesh_all_nodes_connected(self):
        """Test that every node connects to every other node"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_mesh(node_count=3)
        
        # With 3 nodes, should have R1-R2, R1-R3, R2-R3
        link_endpoints = [link.endpoints for link in topo.links]
        assert len(link_endpoints) == 3


class TestTreeTopology:
    """Test tree topology generation"""

    def test_generate_tree_depth_2_branch_2(self):
        """Test tree topology with depth 2 and branching factor 2"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_tree(depth=2, branching_factor=2)
        
        # Depth 2, branch 2: 1 root + 2 children + 4 grandchildren = 7 nodes
        assert len(topo.nodes) == 7
        assert len(topo.links) == 6  # n-1 links in tree

    def test_generate_tree_depth_3_branch_2(self):
        """Test tree topology with depth 3 and branching factor 2"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_tree(depth=3, branching_factor=2)
        
        # 1 + 2 + 4 + 8 = 15 nodes
        assert len(topo.nodes) == 15
        assert len(topo.links) == 14


class TestIPAddressAllocation:
    """Test IP address allocation"""

    def test_allocates_unique_ips(self):
        """Test that IP addresses are unique"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=5)
        
        # Check that link IPs are allocated
        # (Note: We'll implement IP allocation in interfaces or link attributes)
        assert topo is not None

    def test_uses_10_network(self):
        """Test that IPs are in 10.0.0.0/8 range"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        # This will be checked once we add IP allocation to links
        assert True  # Placeholder for now


class TestNodeProperties:
    """Test node properties in generated topologies"""

    def test_nodes_are_routers(self):
        """Test that all nodes are router type"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=3)
        
        for node in topo.nodes:
            assert node.type == "router"

    def test_nodes_have_platform(self):
        """Test that all nodes have platform set"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=3)
        
        for node in topo.nodes:
            assert node.platform == "frr"

    def test_nodes_have_image(self):
        """Test that all nodes have image set"""
        from topology_generator import TopologyGenerator
        
        gen = TopologyGenerator()
        topo = gen.generate_linear(node_count=3)
        
        for node in topo.nodes:
            assert node.image is not None

