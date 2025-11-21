"""
Unit tests for infrastructure layer.
Following TDD: Write tests first, then implement infrastructure providers.

Phase 2: Infrastructure Layer - Containerlab
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from abc import ABC


class TestInfrastructureProviderInterface:
    """Test the abstract base class interface"""

    def test_infrastructure_provider_is_abstract(self):
        """Test that InfrastructureProvider is an abstract base class"""
        from benchmark.infrastructure.base import InfrastructureProvider

        assert issubclass(InfrastructureProvider, ABC)

    def test_infrastructure_provider_has_provision_method(self):
        """Test that provision method exists"""
        from benchmark.infrastructure.base import InfrastructureProvider

        assert hasattr(InfrastructureProvider, "provision")

    def test_infrastructure_provider_has_is_ready_method(self):
        """Test that is_ready method exists"""
        from benchmark.infrastructure.base import InfrastructureProvider

        assert hasattr(InfrastructureProvider, "is_ready")

    def test_infrastructure_provider_has_teardown_method(self):
        """Test that teardown method exists"""
        from benchmark.infrastructure.base import InfrastructureProvider

        assert hasattr(InfrastructureProvider, "teardown")

    def test_infrastructure_provider_has_get_node_container_name_method(self):
        """Test that get_node_container_name method exists"""
        from benchmark.infrastructure.base import InfrastructureProvider

        assert hasattr(InfrastructureProvider, "get_node_container_name")

    def test_cannot_instantiate_abstract_provider(self):
        """Test that we cannot instantiate the abstract class directly"""
        from benchmark.infrastructure.base import InfrastructureProvider

        with pytest.raises(TypeError):
            InfrastructureProvider()


class TestContainerlabYAMLGeneration:
    """Test YAML generation from TopologySpecification"""

    def test_generate_simple_topology_yaml(self):
        """Test generating YAML for a simple 2-node topology"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            Link,
            TopologySpecification,
        )

        # Create a simple topology
        nodes = [
            Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR),
            Node(name="R2", type=NodeType.ROUTER, platform=Platform.FRR),
        ]
        links = [Link(endpoints=["R1:eth1", "R2:eth1"])]
        topology = TopologySpecification(nodes=nodes, links=links)

        provider = ContainerlabProvider()
        topology_id = "test_topo_001"
        yaml_content = provider._generate_clab_yaml(topology, topology_id)

        # Verify YAML structure
        assert "name: " in yaml_content
        assert topology_id in yaml_content
        assert "topology:" in yaml_content
        assert "nodes:" in yaml_content
        assert "R1:" in yaml_content
        assert "R2:" in yaml_content
        assert "links:" in yaml_content

    def test_yaml_includes_node_properties(self):
        """Test that generated YAML includes node properties"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            TopologySpecification,
        )

        nodes = [
            Node(
                name="R1",
                type=NodeType.ROUTER,
                image="frrouting/frr:v8.4.0",
                platform=Platform.FRR,
            )
        ]
        topology = TopologySpecification(nodes=nodes, links=[])

        provider = ContainerlabProvider()
        yaml_content = provider._generate_clab_yaml(topology, "test_topo")

        # Verify node properties in YAML
        assert "frrouting/frr:v8.4.0" in yaml_content
        assert "R1:" in yaml_content

    def test_yaml_includes_links(self):
        """Test that generated YAML includes link definitions"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            Link,
            TopologySpecification,
        )

        nodes = [
            Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR),
            Node(name="R2", type=NodeType.ROUTER, platform=Platform.FRR),
        ]
        links = [Link(endpoints=["R1:eth1", "R2:eth1"])]
        topology = TopologySpecification(nodes=nodes, links=links)

        provider = ContainerlabProvider()
        yaml_content = provider._generate_clab_yaml(topology, "test_topo")

        # Verify links in YAML
        assert "links:" in yaml_content
        assert "R1:eth1" in yaml_content
        assert "R2:eth1" in yaml_content

    def test_yaml_with_multiple_links(self):
        """Test YAML generation with multiple links"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            Link,
            TopologySpecification,
        )

        nodes = [
            Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR),
            Node(name="R2", type=NodeType.ROUTER, platform=Platform.FRR),
            Node(name="R3", type=NodeType.ROUTER, platform=Platform.FRR),
        ]
        links = [
            Link(endpoints=["R1:eth1", "R2:eth1"]),
            Link(endpoints=["R2:eth2", "R3:eth1"]),
        ]
        topology = TopologySpecification(nodes=nodes, links=links)

        provider = ContainerlabProvider()
        yaml_content = provider._generate_clab_yaml(topology, "test_topo")

        # Verify all links present
        assert "R1:eth1" in yaml_content
        assert "R2:eth1" in yaml_content
        assert "R2:eth2" in yaml_content
        assert "R3:eth1" in yaml_content


class TestTopologyIDGeneration:
    """Test topology ID generation and uniqueness"""

    def test_topology_id_generation(self):
        """Test that topology IDs are generated"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        provider = ContainerlabProvider()
        topology_id = provider._generate_topology_id()

        assert topology_id is not None
        assert isinstance(topology_id, str)
        assert len(topology_id) > 0

    def test_topology_ids_are_unique(self):
        """Test that generated topology IDs are unique"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        provider = ContainerlabProvider()
        id1 = provider._generate_topology_id()
        id2 = provider._generate_topology_id()

        assert id1 != id2

    def test_topology_id_format(self):
        """Test that topology IDs follow expected format"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        provider = ContainerlabProvider()
        topology_id = provider._generate_topology_id()

        # Should contain timestamp or UUID-like format
        # Allow alphanumeric and underscores/dashes
        assert topology_id.replace("_", "").replace("-", "").isalnum()


class TestContainerNameFormatting:
    """Test container name formatting"""

    def test_get_node_container_name(self):
        """Test container name generation for a node"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        provider = ContainerlabProvider()
        topology_id = "test_topo_001"
        node_name = "R1"

        container_name = provider.get_node_container_name(topology_id, node_name)

        # Containerlab naming convention: clab-{topology_id}-{node_name}
        assert container_name == f"clab-{topology_id}-{node_name}"

    def test_container_name_with_special_chars(self):
        """Test container name with different node names"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        provider = ContainerlabProvider()
        topology_id = "test_123"
        node_name = "router_1"

        container_name = provider.get_node_container_name(topology_id, node_name)
        assert container_name == f"clab-{topology_id}-{node_name}"


class TestProvisionMethod:
    """Test provision method with mocked subprocess"""

    @patch("benchmark.infrastructure.containerlab.subprocess.run")
    @patch("benchmark.infrastructure.containerlab.tempfile.NamedTemporaryFile")
    def test_provision_success(self, mock_tempfile, mock_subprocess):
        """Test successful topology provision"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            TopologySpecification,
        )

        # Mock temporary file
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_topology.clab.yml"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        # Mock successful subprocess call
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Topology deployed successfully"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Create topology
        nodes = [Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR)]
        topology = TopologySpecification(nodes=nodes, links=[])

        # Provision
        provider = ContainerlabProvider()
        topology_id = provider.provision(topology)

        # Verify
        assert topology_id is not None
        assert isinstance(topology_id, str)
        assert mock_subprocess.called

    @patch("benchmark.infrastructure.containerlab.subprocess.run")
    @patch("benchmark.infrastructure.containerlab.tempfile.NamedTemporaryFile")
    def test_provision_calls_clab_deploy(self, mock_tempfile, mock_subprocess):
        """Test that provision calls 'clab deploy' command"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            TopologySpecification,
        )

        # Mock temporary file
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.clab.yml"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        # Mock successful subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_subprocess.return_value = mock_result

        nodes = [Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR)]
        topology = TopologySpecification(nodes=nodes, links=[])

        provider = ContainerlabProvider()
        provider.provision(topology)

        # Verify clab deploy was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args
        assert "clab" in str(call_args) or "containerlab" in str(call_args)
        assert "deploy" in str(call_args)

    @patch("benchmark.infrastructure.containerlab.subprocess.run")
    @patch("benchmark.infrastructure.containerlab.tempfile.NamedTemporaryFile")
    def test_provision_failure_raises_exception(self, mock_tempfile, mock_subprocess):
        """Test that provision raises exception on failure"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            TopologySpecification,
        )

        # Mock temporary file
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.clab.yml"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        # Mock failed subprocess (non-zero return code)
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error deploying topology"
        mock_subprocess.return_value = mock_result

        nodes = [Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR)]
        topology = TopologySpecification(nodes=nodes, links=[])

        provider = ContainerlabProvider()

        # Should raise exception on failure
        with pytest.raises(Exception):
            provider.provision(topology)


class TestIsReadyMethod:
    """Test is_ready method with mocked Docker SDK"""

    @patch("benchmark.infrastructure.containerlab.docker.from_env")
    def test_is_ready_with_running_containers(self, mock_docker):
        """Test is_ready returns True when all containers are running"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()
        mock_container.status = "running"
        mock_client.containers.list.return_value = [mock_container]
        mock_docker.return_value = mock_client

        provider = ContainerlabProvider()
        topology_id = "test_topo"

        result = provider.is_ready(topology_id)

        assert result is True

    @patch("benchmark.infrastructure.containerlab.docker.from_env")
    def test_is_ready_with_no_containers(self, mock_docker):
        """Test is_ready returns False when no containers found"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        # Mock Docker client with no containers
        mock_client = Mock()
        mock_client.containers.list.return_value = []
        mock_docker.return_value = mock_client

        provider = ContainerlabProvider()
        topology_id = "test_topo"

        result = provider.is_ready(topology_id)

        assert result is False


class TestTeardownMethod:
    """Test teardown method with mocked subprocess"""

    @patch("benchmark.infrastructure.containerlab.subprocess.run")
    def test_teardown_success(self, mock_subprocess):
        """Test successful topology teardown"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        # Mock successful subprocess call
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Topology destroyed"
        mock_subprocess.return_value = mock_result

        provider = ContainerlabProvider()
        topology_id = "test_topo_001"

        result = provider.teardown(topology_id)

        assert result is True
        assert mock_subprocess.called

    @patch("benchmark.infrastructure.containerlab.subprocess.run")
    def test_teardown_calls_clab_destroy(self, mock_subprocess):
        """Test that teardown calls 'clab destroy' command"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        # Mock successful subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        provider = ContainerlabProvider()
        topology_id = "test_topo"

        provider.teardown(topology_id)

        # Verify clab destroy was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args
        assert "clab" in str(call_args) or "containerlab" in str(call_args)
        assert "destroy" in str(call_args)

    @patch("benchmark.infrastructure.containerlab.subprocess.run")
    def test_teardown_with_cleanup_flag(self, mock_subprocess):
        """Test that teardown includes cleanup flag"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        provider = ContainerlabProvider()
        provider.teardown("test_topo")

        # Verify cleanup flag is included
        call_args = mock_subprocess.call_args
        args_str = str(call_args)
        # Should include --cleanup or -c flag
        assert "--cleanup" in args_str or "-c" in args_str

    @patch("benchmark.infrastructure.containerlab.subprocess.run")
    def test_teardown_handles_failure_gracefully(self, mock_subprocess):
        """Test that teardown handles failures gracefully"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        # Mock failed subprocess
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error destroying topology"
        mock_subprocess.return_value = mock_result

        provider = ContainerlabProvider()
        result = provider.teardown("test_topo")

        # Should return False but not raise exception
        assert result is False

    @patch("benchmark.infrastructure.containerlab.docker.from_env")
    def test_cleanup_docker_networks_removes_matching_networks(self, mock_docker):
        """Test that _cleanup_docker_networks removes networks with matching topology_id"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        # Mock Docker client and networks
        mock_client = Mock()
        mock_network1 = Mock()
        mock_network1.name = "bench_1234567890_abcdef12"
        mock_network2 = Mock()
        mock_network2.name = "bench_1234567890_abcdef12"  # Same as topology_id
        mock_network3 = Mock()
        mock_network3.name = "other_network"
        
        mock_client.networks.list.return_value = [mock_network1, mock_network2, mock_network3]
        mock_docker.return_value = mock_client

        provider = ContainerlabProvider()
        topology_id = "bench_1234567890_abcdef12"
        
        # Call the private method
        provider._cleanup_docker_networks(topology_id)
        
        # Verify that networks with matching names were removed
        assert mock_network1.remove.called
        assert mock_network2.remove.called
        assert not mock_network3.remove.called

    @patch("benchmark.infrastructure.containerlab.docker.from_env")
    def test_cleanup_docker_networks_handles_docker_client_failure(self, mock_docker):
        """Test that _cleanup_docker_networks falls back to CLI when Docker client fails"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        # Mock Docker client to raise exception
        mock_docker.side_effect = Exception("Docker client failed")
        
        provider = ContainerlabProvider()
        topology_id = "bench_1234567890_abcdef12"
        
        # Should not raise exception even if Docker client fails
        provider._cleanup_docker_networks(topology_id)


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_provision_with_empty_topology(self):
        """Test provisioning with minimal topology"""
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.task import (
            Node,
            NodeType,
            Platform,
            TopologySpecification,
        )

        # Single node, no links
        nodes = [Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR)]
        topology = TopologySpecification(nodes=nodes, links=[])

        provider = ContainerlabProvider()
        yaml_content = provider._generate_clab_yaml(topology, "test")

        # Should generate valid YAML even with no links
        assert "R1:" in yaml_content
        assert "topology:" in yaml_content

