"""
Containerlab infrastructure provider implementation.

This module implements the InfrastructureProvider interface for Containerlab,
enabling dynamic topology provisioning and management.
"""
import os
import random
import subprocess
import tempfile
import time
import uuid
from typing import Dict, Any
import yaml
import docker

from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.models.task import TopologySpecification


class ContainerlabProvider(InfrastructureProvider):
    """
    Containerlab infrastructure provider.
    
    Implements topology provisioning using Containerlab (https://containerlab.dev/).
    Generates .clab.yml files dynamically and manages topology lifecycle.
    """

    def __init__(self, cleanup_stale_networks: bool = True):
        """
        Initialize the Containerlab provider.
        
        Args:
            cleanup_stale_networks: If True, clean up any stale benchmark networks
                                   from previous runs on initialization
        """
        self.docker_client = None
        self.temp_files = {}  # Track temp files for cleanup
        
        # Clean up stale networks from previous runs
        if cleanup_stale_networks:
            self._cleanup_stale_benchmark_networks()

    def _generate_topology_id(self) -> str:
        """
        Generate a unique topology identifier.
        
        Returns:
            Unique topology ID (UUID-based with timestamp)
        """
        timestamp = str(int(time.time()))
        unique_id = str(uuid.uuid4())[:8]
        return f"bench_{timestamp}_{unique_id}"

    def _generate_clab_yaml(
        self, topology: TopologySpecification, topology_id: str
    ) -> str:
        """
        Generate Containerlab YAML configuration from TopologySpecification.
        
        Args:
            topology: TopologySpecification model
            topology_id: Unique topology identifier
            
        Returns:
            YAML configuration as string
        """
        # Build the containerlab configuration structure
        # Use a high subnet range (172.100.x.x) to avoid conflicts with common networks
        subnet_third_octet = random.randint(100, 250)
        
        clab_config: Dict[str, Any] = {
            "name": topology_id,
            "mgmt": {
                "network": topology_id,  # Use unique network name
                "ipv4-subnet": f"172.{subnet_third_octet}.20.0/24",  # Random high subnet
            },
            "topology": {
                "nodes": {},
                "links": [],
            },
        }

        # Add nodes
        for node in topology.nodes:
            clab_config["topology"]["nodes"][node.name] = {
                "kind": "linux",  # Containerlab node kind
                "image": node.image,
            }

        # Add links
        for link in topology.links:
            clab_config["topology"]["links"].append(
                {"endpoints": link.endpoints}
            )

        # Convert to YAML string
        yaml_content = yaml.dump(clab_config, default_flow_style=False, sort_keys=False)
        return yaml_content

    def provision(self, topology: TopologySpecification) -> str:
        """
        Provision a topology using Containerlab.
        
        Generates a .clab.yml file and executes 'clab deploy' command.
        
        Args:
            topology: TopologySpecification model
            
        Returns:
            topology_id: Unique identifier for the provisioned topology
            
        Raises:
            Exception: If provisioning fails after retries
        """
        # Generate unique topology ID
        topology_id = self._generate_topology_id()

        # Generate YAML configuration
        yaml_content = self._generate_clab_yaml(topology, topology_id)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".clab.yml", delete=False
        ) as f:
            f.write(yaml_content)
            temp_file_path = f.name

        # Store temp file path for cleanup
        self.temp_files[topology_id] = temp_file_path

        try:
            # Execute containerlab deploy command
            # Try without sudo first (works in most setups)
            cmd = ["clab", "deploy", "-t", temp_file_path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )
            
            # If permission denied, try with sudo
            if result.returncode != 0 and "permission denied" in result.stderr.lower():
                cmd = ["sudo", "-n", "clab", "deploy", "-t", temp_file_path]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )


            if result.returncode != 0:
                error_msg = f"Containerlab deploy failed: {result.stderr}"
                # Clean up temp file on failure
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                del self.temp_files[topology_id]
                raise Exception(error_msg)

            return topology_id

        except subprocess.TimeoutExpired:
            # Clean up temp file on timeout
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if topology_id in self.temp_files:
                del self.temp_files[topology_id]
            raise Exception("Containerlab deploy timed out after 5 minutes")
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if topology_id in self.temp_files:
                del self.temp_files[topology_id]
            raise Exception(f"Failed to provision topology: {str(e)}")

    def is_ready(self, topology_id: str) -> bool:
        """
        Check if topology is ready by verifying all containers are running.
        
        Args:
            topology_id: Unique topology identifier
            
        Returns:
            True if all containers are running, False otherwise
        """
        try:
            # Initialize Docker client if needed
            if self.docker_client is None:
                self.docker_client = docker.from_env()

            # List containers with the topology name prefix
            containers = self.docker_client.containers.list(
                filters={"name": f"clab-{topology_id}"}
            )

            # If no containers found, topology is not ready
            if not containers:
                return False

            # Check if all containers are running
            all_running = all(
                container.status == "running" for container in containers
            )

            return all_running

        except Exception:
            # If we can't check, assume not ready
            return False

    def teardown(self, topology_id: str) -> bool:
        """
        Teardown (destroy) a Containerlab topology.
        
        Executes 'clab destroy' command with cleanup flag and removes Docker networks.
        This method is robust and will attempt cleanup even if the destroy command fails.
        
        Args:
            topology_id: Unique topology identifier
            
        Returns:
            True if teardown successful, False otherwise
        """
        destroy_success = False
        
        try:
            # Execute containerlab destroy command using topology name
            # Try without sudo first
            cmd = ["clab", "destroy", "--name", topology_id, "--cleanup"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes timeout
            )
            
            # If permission denied, try with sudo
            if result.returncode != 0 and "permission denied" in result.stderr.lower():
                cmd = ["sudo", "-n", "clab", "destroy", "--name", topology_id, "--cleanup"]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            
            destroy_success = (result.returncode == 0)

        except Exception as e:
            # Log error but don't raise - teardown should be best-effort
            destroy_success = False
        
        # ALWAYS attempt cleanup, even if destroy failed
        try:
            # CRITICAL: Clean up Docker networks manually
            # The --cleanup flag only removes lab directories, not always networks
            self._cleanup_docker_networks(topology_id)
            
            # Also try to force remove any containers that might still be running
            self._cleanup_containers(topology_id)

            # Clean up temporary file if it exists
            if topology_id in self.temp_files:
                temp_file_path = self.temp_files[topology_id]
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                del self.temp_files[topology_id]

        except Exception:
            # Best effort cleanup - continue even if this fails
            pass
        
        return destroy_success
    
    def _cleanup_containers(self, topology_id: str) -> None:
        """
        Force remove any containers associated with this topology.
        
        Args:
            topology_id: The topology identifier
        """
        try:
            # Get Docker client
            if self.docker_client is None:
                self.docker_client = docker.from_env()
            
            # List all containers (including stopped ones)
            containers = self.docker_client.containers.list(all=True)
            
            # Find containers with names matching: clab-{topology_id}-*
            pattern = f"clab-{topology_id}-"
            for container in containers:
                if container.name.startswith(pattern):
                    try:
                        # Force remove the container
                        container.remove(force=True)
                    except Exception:
                        pass
        except Exception:
            # If Docker client fails, try using docker CLI
            try:
                # List containers with pattern and force remove them
                result = subprocess.run(
                    ["docker", "ps", "-a", "--filter", f"name=clab-{topology_id}-", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    container_names = result.stdout.strip().split('\n')
                    for container_name in container_names:
                        try:
                            subprocess.run(
                                ["docker", "rm", "-f", container_name],
                                capture_output=True,
                                timeout=30
                            )
                        except Exception:
                            pass
            except Exception:
                pass  # Best effort

    def _cleanup_stale_benchmark_networks(self) -> None:
        """
        Clean up all stale Docker networks from previous benchmark runs.
        
        This method removes all networks with the 'bench_' prefix that may have
        been left behind from interrupted or failed teardowns. Called on initialization
        to ensure a clean state.
        """
        try:
            # Get Docker client
            if self.docker_client is None:
                self.docker_client = docker.from_env()
            
            # List all networks
            networks = self.docker_client.networks.list()
            
            # Find all benchmark networks (those starting with 'bench_')
            stale_networks = []
            for network in networks:
                if network.name.startswith("bench_"):
                    # Check if there are any containers connected
                    # Only remove if no containers are using it
                    network.reload()  # Refresh network state
                    if len(network.containers) == 0:
                        stale_networks.append(network)
            
            # Remove stale networks
            removed_count = 0
            for network in stale_networks:
                try:
                    network.remove()
                    removed_count += 1
                except Exception:
                    # Network might be in use or already removed
                    pass
            
            if removed_count > 0:
                print(f"🧹 Cleaned up {removed_count} stale benchmark network(s)")
                    
        except Exception:
            # If Docker client fails, try using docker CLI
            try:
                # List benchmark networks via CLI
                result = subprocess.run(
                    ["docker", "network", "ls", "--filter", "name=bench_", "--format", "{{.Name}}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    network_names = result.stdout.strip().split('\n')
                    removed_count = 0
                    for network_name in network_names:
                        try:
                            subprocess.run(
                                ["docker", "network", "rm", network_name],
                                capture_output=True,
                                timeout=30
                            )
                            removed_count += 1
                        except Exception:
                            pass
                    
                    if removed_count > 0:
                        print(f"🧹 Cleaned up {removed_count} stale benchmark network(s)")
            except Exception:
                # Best effort - if this fails, we'll just continue
                pass

    def _cleanup_docker_networks(self, topology_id: str) -> None:
        """
        Clean up Docker networks created by Containerlab for this topology.
        
        Containerlab creates networks with the pattern: bench_{timestamp}_{hash}
        We need to find and remove networks that match our topology_id.
        
        Args:
            topology_id: The topology identifier to clean up networks for
        """
        try:
            # Get Docker client
            if self.docker_client is None:
                self.docker_client = docker.from_env()
            
            # List all networks
            networks = self.docker_client.networks.list()
            
            # Find networks that match our topology pattern
            # Containerlab creates networks like: bench_{timestamp}_{hash}
            # Our topology_id is: bench_{timestamp}_{hash}
            networks_to_remove = []
            for network in networks:
                if network.name == topology_id:
                    networks_to_remove.append(network)
            
            # Remove matching networks
            for network in networks_to_remove:
                try:
                    network.remove()
                except Exception:
                    # Network might already be removed or in use
                    pass
                    
        except Exception:
            # If Docker client fails, try using docker CLI
            try:
                # Use docker CLI to remove networks
                cmd = ["docker", "network", "rm", topology_id]
                subprocess.run(cmd, capture_output=True, timeout=30)
            except Exception:
                # Best effort - if this fails, we can't do much more
                pass

    def get_node_container_name(self, topology_id: str, node_name: str) -> str:
        """
        Get the Docker container name for a node.
        
        Containerlab naming convention: clab-{topology_id}-{node_name}
        
        Args:
            topology_id: Unique topology identifier
            node_name: Node name from topology
            
        Returns:
            Container name
        """
        return f"clab-{topology_id}-{node_name}"

