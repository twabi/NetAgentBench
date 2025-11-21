"""
Abstract base class for infrastructure providers.

This module defines the interface that all infrastructure providers must implement.
This allows the benchmark to be provider-agnostic (Containerlab, GNS3, EVE-NG, etc.).
"""
from abc import ABC, abstractmethod
from benchmark.models.task import TopologySpecification


class InfrastructureProvider(ABC):
    """
    Abstract base class for infrastructure providers.
    
    Infrastructure providers are responsible for:
    - Provisioning network topologies
    - Managing topology lifecycle
    - Providing access to network nodes
    
    This abstraction allows the benchmark to work with different infrastructure
    backends (Containerlab, GNS3, EVE-NG, physical devices, etc.) without
    changing the core benchmark logic.
    """

    @abstractmethod
    def provision(self, topology: TopologySpecification) -> str:
        """
        Provision a network topology.
        
        Args:
            topology: TopologySpecification model defining the network
            
        Returns:
            topology_id: Unique identifier for the provisioned topology
            
        Raises:
            Exception: If provisioning fails
        """
        pass

    @abstractmethod
    def is_ready(self, topology_id: str) -> bool:
        """
        Check if a topology is ready for use.
        
        Args:
            topology_id: Unique identifier for the topology
            
        Returns:
            True if all nodes are running and ready, False otherwise
        """
        pass

    @abstractmethod
    def teardown(self, topology_id: str) -> bool:
        """
        Teardown (destroy) a provisioned topology.
        
        Args:
            topology_id: Unique identifier for the topology
            
        Returns:
            True if teardown successful, False otherwise
        """
        pass

    @abstractmethod
    def get_node_container_name(self, topology_id: str, node_name: str) -> str:
        """
        Get the container/instance name for a specific node.
        
        Different providers may use different naming conventions.
        This method provides a consistent way to get the actual
        container/instance name for command execution.
        
        Args:
            topology_id: Unique identifier for the topology
            node_name: Name of the node as defined in topology
            
        Returns:
            Container/instance name for the node
        """
        pass

