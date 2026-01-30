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
import shutil

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
        self.temp_dirs = {}  # Track temp dirs for cleanup
        
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
        self, topology: TopologySpecification, topology_id: str, config_dir: str
    ) -> str:
        """
        Generate Containerlab YAML configuration from TopologySpecification.
        
        Args:
            topology: TopologySpecification model
            topology_id: Unique topology identifier
            config_dir: Directory where config files are stored
            
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
            node_config = {
                "image": node.image,
            }

            # Determine kind and binds based on platform
            if node.platform == "nokia_srl":
                node_config["kind"] = "nokia_srlinux"
            elif node.platform == "arista_eos":
                node_config["kind"] = "arista_ceos"
            elif node.platform == "cisco_ios_xe":
                node_config["kind"] = "vr-cisco_csr1000v" # Supported VRNetLab kind for IOS-XE
            elif node.platform == "frr":
                node_config["kind"] = "linux"
                # Add binds for FRR configuration
                node_config["binds"] = [
                    f"{config_dir}/daemons:/etc/frr/daemons:ro",
                    f"{config_dir}/vtysh.conf:/etc/frr/vtysh.conf:ro"
                ]
                # Default cmd to start nothing or let image handle it? 
                # FRR image usually starts zebra/bgpd if daemons enabled.
            else:
                node_config["kind"] = "linux"
                # For generic linux (alpine), ensure basic tools are present
                if "alpine" in node.image:
                    node_config["exec"] = [
                        "apk add --no-cache iptables iproute2"
                    ]
        
            clab_config["topology"]["nodes"][node.name] = node_config

        # Add links
        for link in topology.links:
            clab_config["topology"]["links"].append(
                {"endpoints": link.endpoints}
            )

        # Convert to YAML string
        yaml_content = yaml.dump(clab_config, default_flow_style=False, sort_keys=False)
        return yaml_content

    def _create_frr_configs(self, config_dir: str) -> None:
        """Create default FRR configuration files."""
        # Create daemons file
        daemons_content = """
bgpd=yes
ospfd=yes
ospf6d=yes
ripd=yes
ripngd=yes
isisd=yes
pimd=yes
ldpd=yes
nhrpd=yes
eigrpd=yes
babeld=yes
sharpd=yes
pbrd=yes
bfdd=yes
fabricd=yes
vrrpd=yes
pathd=yes
"""
        with open(f"{config_dir}/daemons", "w") as f:
            f.write(daemons_content.strip())

        # Create vtysh.conf
        vtysh_content = """
service integrated-vtysh-config
"""
        with open(f"{config_dir}/vtysh.conf", "w") as f:
            f.write(vtysh_content.strip())

    def provision(self, topology: TopologySpecification) -> str:
        """
        Provision a topology using Containerlab.
        
        Args:
            topology: TopologySpecification model
            
        Returns:
            topology_id: Unique identifier for the provisioned topology
            
        Raises:
            Exception: If provisioning fails after retries
        """
        # Generate unique topology ID
        topology_id = self._generate_topology_id()

        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"clab_{topology_id}_")
        self.temp_dirs[topology_id] = temp_dir

        try:
            # Create aux config files if needed (e.g. for FRR)
            # We create them regardless of platform presence to be safe/simple, 
            # or check if any node is FRR. Optimizing: just create them.
            self._create_frr_configs(temp_dir)

            # Generate YAML configuration
            yaml_content = self._generate_clab_yaml(topology, topology_id, temp_dir)

            # Write config to file
            clab_file = f"{temp_dir}/{topology_id}.clab.yml"
            with open(clab_file, "w") as f:
                f.write(yaml_content)

            # Execute containerlab deploy command
            cmd = ["clab", "deploy", "-t", clab_file]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )
            
            # If permission denied, try with sudo
            if result.returncode != 0 and "permission denied" in result.stderr.lower():
                cmd = ["sudo", "-n", "clab", "deploy", "-t", clab_file]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

            if result.returncode != 0:
                error_msg = f"Containerlab deploy failed: {result.stderr}"
                # Try to clean up any partially created resources
                try:
                    self.teardown(topology_id)
                except:
                    pass
                raise Exception(error_msg)

            return topology_id

        except Exception as e:
            # Ensure teardown is called if we haven't already
            try:
                self.teardown(topology_id)
            except:
                pass
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
            # Execute destroy command
            # Pass full path to clab file if we have it?
            # Or just name. 'clab destroy --name ...' works if name matches.
            cmd = ["clab", "destroy", "--name", topology_id, "--cleanup"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0 and "permission denied" in result.stderr.lower():
                 cmd = ["sudo", "-n", "clab", "destroy", "--name", topology_id, "--cleanup"]
                 result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            destroy_success = (result.returncode == 0)

        except Exception:
            destroy_success = False
        
        # Cleanup tasks
        try:
            self._cleanup_containers(topology_id)
            self._cleanup_docker_networks(topology_id)

            # Clean up temp directory
            if topology_id in self.temp_dirs:
                temp_dir = self.temp_dirs[topology_id]
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                del self.temp_dirs[topology_id]

        except Exception:
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
                    # Force remove any containers still attached to this network
                    try:
                        network.reload()
                        if network.containers:
                            for container in network.containers:
                                try:
                                    container.remove(force=True)
                                except:
                                    pass
                    except:
                        pass
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

