"""
Integration tests for Containerlab infrastructure provider.

These tests run against REAL Containerlab and Docker, not mocks.

Requirements:
- Containerlab installed and accessible via 'sudo clab'
- Docker installed and running
- sudo access (no password prompt for clab commands)
- Network access to pull container images

WARNING: These tests create actual containers and may take 30-60 seconds to run.
"""
import pytest
import time
import subprocess

from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.models.task import (
    Node,
    NodeType,
    Platform,
    Link,
    TopologySpecification,
)


@pytest.fixture
def simple_topology():
    """Create a simple single-node topology for testing"""
    nodes = [
        Node(
            name="test_node",
            type=NodeType.LINUX,
            image="alpine:latest",  # Small, fast image
            platform=Platform.FRR,
        )
    ]
    return TopologySpecification(nodes=nodes, links=[])


@pytest.fixture
def two_node_topology():
    """Create a two-node topology with a link"""
    nodes = [
        Node(
            name="node1",
            type=NodeType.LINUX,
            image="alpine:latest",
            platform=Platform.FRR,
        ),
        Node(
            name="node2",
            type=NodeType.LINUX,
            image="alpine:latest",
            platform=Platform.FRR,
        ),
    ]
    links = [Link(endpoints=["node1:eth1", "node2:eth1"])]
    return TopologySpecification(nodes=nodes, links=links)


def check_containerlab_available():
    """Check if containerlab is available"""
    try:
        # Try without sudo first (preferred)
        result = subprocess.run(
            ["clab", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True
        
        # Try with sudo (if needed)
        result = subprocess.run(
            ["sudo", "-n", "clab", "version"],  # -n means non-interactive
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_docker_available():
    """Check if Docker is available"""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


# Skip all tests if containerlab or docker is not available
pytestmark = pytest.mark.skipif(
    not check_containerlab_available() or not check_docker_available(),
    reason="Containerlab or Docker not available",
)


@pytest.mark.integration
class TestContainerlabProvisionSingleNode:
    """Test provisioning a single-node topology"""

    def test_provision_single_node_success(self, simple_topology):
        """Test provisioning a simple single-node topology"""
        provider = ContainerlabProvider()
        topology_id = None

        try:
            # Provision topology
            topology_id = provider.provision(simple_topology)

            # Verify topology_id returned
            assert topology_id is not None
            assert isinstance(topology_id, str)
            assert len(topology_id) > 0

            # Verify topology_id format (should be bench_timestamp_uuid)
            assert topology_id.startswith("bench_")
            parts = topology_id.split("_")
            assert len(parts) == 3  # bench, timestamp, uuid

        finally:
            # Always cleanup, even if test fails
            if topology_id:
                provider.teardown(topology_id)

    def test_is_ready_returns_true_for_running_topology(self, simple_topology):
        """Test that is_ready() returns True when topology is running"""
        provider = ContainerlabProvider()
        topology_id = None

        try:
            # Provision topology
            topology_id = provider.provision(simple_topology)

            # Give containers time to start
            time.sleep(3)

            # Check if ready
            is_ready = provider.is_ready(topology_id)

            # Should be ready
            assert is_ready is True

        finally:
            if topology_id:
                provider.teardown(topology_id)

    def test_get_container_name_matches_actual_container(self, simple_topology):
        """Test that get_node_container_name returns the actual container name"""
        provider = ContainerlabProvider()
        topology_id = None

        try:
            # Provision topology
            topology_id = provider.provision(simple_topology)
            time.sleep(3)

            # Get container name
            container_name = provider.get_node_container_name(topology_id, "test_node")

            # Verify format
            expected_name = f"clab-{topology_id}-test_node"
            assert container_name == expected_name

            # Verify container actually exists with this name
            import docker
            client = docker.from_env()
            try:
                container = client.containers.get(container_name)
                assert container is not None
                assert container.status in ["running", "created"]
            except docker.errors.NotFound:
                pytest.fail(f"Container {container_name} not found in Docker")

        finally:
            if topology_id:
                provider.teardown(topology_id)

    def test_teardown_removes_topology(self, simple_topology):
        """Test that teardown successfully removes the topology"""
        provider = ContainerlabProvider()

        # Provision topology
        topology_id = provider.provision(simple_topology)
        time.sleep(3)

        # Verify it's running
        assert provider.is_ready(topology_id) is True

        # Teardown
        result = provider.teardown(topology_id)

        # Verify teardown succeeded
        assert result is True

        # Wait a bit for cleanup
        time.sleep(2)

        # Verify containers are gone
        assert provider.is_ready(topology_id) is False


@pytest.mark.integration
class TestContainerlabProvisionTwoNodes:
    """Test provisioning multi-node topologies"""

    def test_provision_two_nodes_with_link(self, two_node_topology):
        """Test provisioning a two-node topology with a link"""
        provider = ContainerlabProvider()
        topology_id = None

        try:
            # Provision topology
            topology_id = provider.provision(two_node_topology)

            # Give containers time to start
            time.sleep(5)

            # Check if ready
            is_ready = provider.is_ready(topology_id)
            assert is_ready is True

            # Verify both containers exist
            import docker
            client = docker.from_env()

            container1_name = provider.get_node_container_name(topology_id, "node1")
            container2_name = provider.get_node_container_name(topology_id, "node2")

            container1 = client.containers.get(container1_name)
            container2 = client.containers.get(container2_name)

            assert container1 is not None
            assert container2 is not None
            assert container1.status == "running"
            assert container2.status == "running"

        finally:
            if topology_id:
                provider.teardown(topology_id)


@pytest.mark.integration
class TestContainerlabErrorHandling:
    """Test error handling scenarios"""

    def test_provision_with_invalid_image_fails_gracefully(self):
        """Test that provision fails gracefully with invalid image"""
        provider = ContainerlabProvider()

        # Create topology with non-existent image
        nodes = [
            Node(
                name="test_node",
                type=NodeType.LINUX,
                image="nonexistent/image:invalid",
                platform=Platform.FRR,
            )
        ]
        topology = TopologySpecification(nodes=nodes, links=[])

        # Should raise exception
        with pytest.raises(Exception) as exc_info:
            provider.provision(topology)

        # Error message should mention the failure
        assert "Failed to provision" in str(exc_info.value) or "deploy failed" in str(
            exc_info.value
        )

    def test_is_ready_returns_false_for_nonexistent_topology(self):
        """Test that is_ready returns False for non-existent topology"""
        provider = ContainerlabProvider()

        # Check non-existent topology
        is_ready = provider.is_ready("nonexistent_topology_12345")

        # Should return False, not raise exception
        assert is_ready is False

    def test_teardown_nonexistent_topology_returns_false(self):
        """Test that teardown of non-existent topology returns False"""
        provider = ContainerlabProvider()

        # Try to teardown non-existent topology
        result = provider.teardown("nonexistent_topology_12345")

        # Should return False (best-effort), not raise exception
        assert result is False


@pytest.mark.integration
class TestContainerlabYAMLGeneration:
    """Test that generated YAML is valid for Containerlab"""

    def test_generated_yaml_is_valid(self, simple_topology):
        """Test that the generated YAML can be parsed and deployed"""
        provider = ContainerlabProvider()
        topology_id = None

        try:
            # Generate YAML
            yaml_content = provider._generate_clab_yaml(
                simple_topology, "test_yaml_validation"
            )

            # Verify YAML structure
            import yaml
            config = yaml.safe_load(yaml_content)

            # Verify required fields
            assert "name" in config
            assert config["name"] == "test_yaml_validation"
            assert "topology" in config
            assert "nodes" in config["topology"]
            assert "test_node" in config["topology"]["nodes"]
            assert "image" in config["topology"]["nodes"]["test_node"]
            assert config["topology"]["nodes"]["test_node"]["image"] == "alpine:latest"

        finally:
            # No cleanup needed, just YAML generation
            pass


@pytest.mark.integration
class TestContainerlabLifecycle:
    """Test complete lifecycle: provision → ready → use → teardown"""

    def test_complete_lifecycle(self, simple_topology):
        """Test the complete lifecycle of a topology"""
        provider = ContainerlabProvider()
        topology_id = None

        try:
            # Step 1: Provision
            print("\n[Step 1] Provisioning topology...")
            topology_id = provider.provision(simple_topology)
            assert topology_id is not None
            print(f"[Step 1] Provisioned with ID: {topology_id}")

            # Step 2: Wait for ready
            print("[Step 2] Waiting for topology to be ready...")
            max_wait = 30  # seconds
            start_time = time.time()
            is_ready = False

            while time.time() - start_time < max_wait:
                if provider.is_ready(topology_id):
                    is_ready = True
                    break
                time.sleep(2)

            assert is_ready is True
            print(f"[Step 2] Topology ready after {time.time() - start_time:.1f}s")

            # Step 3: Verify container exists and is accessible
            print("[Step 3] Verifying container accessibility...")
            import docker
            client = docker.from_env()
            container_name = provider.get_node_container_name(topology_id, "test_node")
            container = client.containers.get(container_name)
            assert container.status == "running"
            print(f"[Step 3] Container {container_name} is running")

            # Step 4: Execute a simple command to verify it works
            print("[Step 4] Testing command execution...")
            exec_result = container.exec_run("echo 'Hello from container'")
            assert exec_result.exit_code == 0
            assert b"Hello from container" in exec_result.output
            print("[Step 4] Command execution successful")

            # Step 5: Teardown
            print("[Step 5] Tearing down topology...")
            teardown_result = provider.teardown(topology_id)
            assert teardown_result is True
            print("[Step 5] Teardown successful")

            # Step 6: Verify cleanup
            print("[Step 6] Verifying cleanup...")
            time.sleep(2)
            assert provider.is_ready(topology_id) is False
            print("[Step 6] Cleanup verified - topology removed")

        finally:
            # Emergency cleanup if something failed
            if topology_id and provider.is_ready(topology_id):
                print("\n[Emergency cleanup] Cleaning up failed test...")
                provider.teardown(topology_id)

