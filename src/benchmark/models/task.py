"""
Pydantic models for task definitions.

This module defines all models related to task specifications including:
- Topology (nodes, links, interfaces)
- Intent (properties and evaluation procedures)
- Configuration (convergence settings, optimal solutions)

Based on the FSM formalization document.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enumerations (Platform and Node Types)
# ============================================================================


class Platform(str, Enum):
    """Supported network platforms (Definition 12 in formalization)"""

    FRR = "frr"
    CISCO_IOS = "cisco_ios"
    JUNIPER_JUNOS = "juniper_junos"
    VYOS = "vyos"
    
    # Added for Phase 2
    NOKIA_SRL = "nokia_srl"
    ARISTA_EOS = "arista_eos"
    CISCO_IOS_XE = "cisco_ios_xe"
    LINUX = "linux"

    # Richer platform options (commented out for future use)
    # # Open Source
    # SONIC = "sonic"
    # CUMULUS_LINUX = "cumulus_linux"
    # OPENSWITCH = "openswitch"
    # PICA8 = "pica8"
    # 
    # # Cisco
    # CISCO_IOS_XE = "cisco_ios_xe"
    # CISCO_IOS_XR = "cisco_ios_xr"
    # CISCO_NXOS = "cisco_nxos"
    # CISCO_ASA = "cisco_asa"
    # 
    # # Juniper
    # JUNIPER_JUNOS_EVOLVED = "juniper_junos_evolved"
    # 
    # # Arista
    # ARISTA_EOS = "arista_eos"
    # 
    # # Nokia
    # NOKIA_SROS = "nokia_sros"
    # 
    # # Huawei
    # HUAWEI_VRP = "huawei_vrp"
    # 
    # # SDN/Controller Platforms
    # OPENDAYLIGHT = "opendaylight"
    # ONOS = "onos"
    # P4 = "p4"


class NodeType(str, Enum):
    """Types of network nodes"""

    ROUTER = "router"
    SWITCH = "switch"
    HOST = "host"
    LINUX = "linux"

    # Richer node type options (commented out for future use)
    # # Core Infrastructure
    # FIREWALL = "firewall"
    # LOAD_BALANCER = "load_balancer"
    # 
    # # Specialized Devices
    # WAN_OPTIMIZER = "wan_optimizer"
    # SD_WAN_CONTROLLER = "sd_wan_controller"
    # ACCESS_POINT = "access_point"
    # WIRELESS_CONTROLLER = "wireless_controller"
    # 
    # # Host Types
    # WINDOWS = "windows"
    # SERVER = "server"
    # 
    # # Virtual/Container
    # VIRTUAL_ROUTER = "virtual_router"
    # VIRTUAL_SWITCH = "virtual_switch"
    # CONTAINER = "container"
    # 
    # # SDN
    # SDN_CONTROLLER = "sdn_controller"
    # P4_SWITCH = "p4_switch"


class PropertyType(str, Enum):
    """Types of network properties (Definition 10 in formalization)"""

    REACHABILITY = "reachability"
    BGP_CONFIGURATION = "bgp_configuration"
    ROUTE_EXISTS = "route_exists"
    OSPF_CONFIGURATION = "ospf_configuration"
    INTERFACE_UP = "interface_up"
    
    # Layer 2 Configuration
    VLAN_CONFIGURATION = "vlan_configuration"
    TRUNK_CONFIGURATION = "trunk_configuration"
    SVI_CONFIGURATION = "svi_configuration"
    
    # Security
    ACL_CONFIGURATION = "acl_configuration"
    ACL_RULE = "acl_rule"
    ACL_INTERFACE_BINDING = "acl_interface_binding"
    
    # Firewall
    FIREWALL_RULE = "firewall_rule"
    FIREWALL_BLOCK = "firewall_block"
    
    # Route Redistribution
    ROUTE_REDISTRIBUTION = "route_redistribution"

    # Richer property type options (commented out for future use)
    # # Basic Connectivity
    # INTERFACE_DOWN = "interface_down"
    # 
    # # Routing Protocols
    # BGP_ROUTE = "bgp_route"
    # BGP_PEER_STATE = "bgp_peer_state"
    # OSPF_LSA = "ospf_lsa"
    # ISIS_ADJACENCY = "isis_adjacency"
    # ISIS_LSP = "isis_lsp"
    # 
    # # Route Management
    # ROUTE_PREFERENCE = "route_preference"
    # ROUTE_METRIC = "route_metric"
    # FORWARDING_TABLE = "forwarding_table"
    # 
    # # Layer 2
    # VLAN_MEMBERSHIP = "vlan_membership"
    # STP_STATE = "stp_state"
    # STP_ROOT_BRIDGE = "stp_root_bridge"
    # LLDP_NEIGHBOR = "lldp_neighbor"
    # CDP_NEIGHBOR = "cdp_neighbor"
    # 
    # # MPLS
    # MPLS_LSP = "mpls_lsp"
    # MPLS_TUNNEL = "mpls_tunnel"
    # MPLS_LABEL = "mpls_label"
    # 
    # # Security
    # ACL_RULE = "acl_rule"
    # FIREWALL_RULE = "firewall_rule"
    # IPSEC_TUNNEL = "ipsec_tunnel"
    # 
    # # QoS
    # QoS_POLICY = "qos_policy"
    # TRAFFIC_SHAPING = "traffic_shaping"
    # BANDWIDTH_LIMIT = "bandwidth_limit"
    # 
    # # Load Balancing
    # LOAD_BALANCE_POOL = "load_balance_pool"
    # HEALTH_CHECK = "health_check"
    # 
    # # Wireless
    # WIFI_SSID = "wifi_ssid"
    # WIFI_CLIENT = "wifi_client"
    # WIFI_SIGNAL_STRENGTH = "wifi_signal_strength"


# ============================================================================
# Infrastructure Layer Models (Definitions 3-7 in formalization)
# ============================================================================


class Node(BaseModel):
    """
    Network node specification.
    
    Represents a single network device in the topology.
    """

    name: str = Field(..., description="Unique node identifier")
    type: NodeType = Field(..., description="Node type")
    image: str = Field(
        default="frrouting/frr:latest", description="Container image"
    )
    platform: Platform = Field(default=Platform.FRR, description="Network platform")

    model_config = {"use_enum_values": True}


class Interface(BaseModel):
    """Interface configuration for a node"""

    name: str = Field(..., description="Interface name (e.g., 'eth1', 'lo0')")
    ip: Optional[str] = Field(
        None, description="IP address with prefix (e.g., '192.168.1.1/24')"
    )
    mtu: Optional[int] = Field(None, description="MTU size")


class Link(BaseModel):
    """
    Network link specification.
    
    Connects two node interfaces using endpoint format "node:interface".
    """

    endpoints: List[str] = Field(
        ..., description="Two endpoints in format 'node:interface'"
    )


class TopologySpecification(BaseModel):
    """
    Topology specification T ∈ Σ_infra^+ (Definition 7 in formalization).
    
    Defines the network topology including nodes, links, and interface configurations.
    """

    nodes: List[Node] = Field(..., min_length=1, description="Network nodes")
    links: List[Link] = Field(default_factory=list, description="Network links")
    interfaces: List[Interface] = Field(
        default_factory=list, description="Interface configurations"
    )

    @field_validator("nodes")
    @classmethod
    def validate_unique_node_names(cls, v: List[Node]) -> List[Node]:
        """Validate that node names are unique"""
        names = [node.name for node in v]
        if len(names) != len(set(names)):
            raise ValueError("Node names must be unique")
        return v

    @field_validator("links")
    @classmethod
    def validate_links_reference_nodes(
        cls, v: List[Link], info
    ) -> List[Link]:
        """Validate that links reference existing nodes"""
        # Get nodes from the model data
        if 'nodes' not in info.data:
            return v

        node_names = {node.name for node in info.data['nodes']}

        for link in v:
            for endpoint in link.endpoints:
                # Parse endpoint format "node:interface"
                if ":" not in endpoint:
                    raise ValueError(
                        f"Link endpoint must be in format 'node:interface', got: {endpoint}"
                    )

                node_name = endpoint.split(":")[0]
                if node_name not in node_names:
                    raise ValueError(f"Link references unknown node: {node_name}")

        return v


# ============================================================================
# Pre-configuration and Fault Verification Models
# ============================================================================


class PreconfigurationStep(BaseModel):
    """
    A single step in the pre-configuration sequence.
    """

    node: str = Field(..., description="Node name to execute the command on")
    command: str = Field(..., description="Command string to execute")


# ============================================================================
# Property Evaluation Models (Definitions 10-11 in formalization)
# ============================================================================


class EvaluationProcedure(BaseModel):
    """
    Evaluation procedure specification.
    
    Defines HOW to check a property - this is the key innovation that makes
    the benchmark task-driven and platform-agnostic.
    """

    method: str = Field(
        ..., description="Evaluation method (e.g., 'exec_and_parse')"
    )
    target_node: str = Field(..., description="Node to execute evaluation on")
    command: str = Field(..., description="Command to execute")
    parser: str = Field(
        ..., description="Parser type: 'json', 'regex', 'text'"
    )
    success_condition: Dict[str, Any] = Field(
        ..., description="Condition that defines success"
    )


class Property(BaseModel):
    """
    Network property p: S × Condition → {true, false} (Definition 10).
    
    A property that must be satisfied for the configuration to be valid.
    """

    id: str = Field(..., description="Unique property identifier")
    type: PropertyType = Field(..., description="Property type")
    description: str = Field(..., description="Human-readable description")
    evaluation: EvaluationProcedure = Field(
        ..., description="How to evaluate this property"
    )

    model_config = {"use_enum_values": True}


class IntentSpecification(BaseModel):
    """
    Intent specification P = {p₁, p₂, ..., pₘ} (Definition 11).
    
    The set of properties that must be satisfied for the configuration
    to achieve the desired network intent.
    """

    properties: List[Property] = Field(
        ..., min_length=1, description="Set of required properties"
    )

    @field_validator("properties")
    @classmethod
    def validate_unique_property_ids(cls, v: List[Property]) -> List[Property]:
        """Validate that property IDs are unique"""
        ids = [prop.id for prop in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Property IDs must be unique")
        return v


# ============================================================================
# Convergence and Optimization Models
# ============================================================================


class ConvergenceConfig(BaseModel):
    """
    Convergence configuration.
    
    Defines timeouts for protocol convergence (Assumption 2 in formalization).
    """

    timeout_seconds: int = Field(
        default=30, description="Maximum time to wait for convergence"
    )
    check_interval_seconds: int = Field(
        default=2, description="Interval between convergence checks"
    )


class OptimalSolution(BaseModel):
    """
    Optimal solution specification (Definition 15).
    
    Optional reference for efficiency scoring.
    """

    command_count: int = Field(..., description="Number of commands in optimal solution")
    description: str = Field(..., description="Description of optimal approach")


# ============================================================================
# Main Task Definition Model
# ============================================================================


class TaskDefinition(BaseModel):
    """
    Complete task definition - the main model.
    
    A task specifies:
    - What topology to provision (infrastructure layer)
    - What intent to achieve (SUT layer)
    - How to evaluate success (property evaluation)
    - Platform-specific information
    
    This is the "source of truth" that drives the entire benchmark.
    """

    task_id: str = Field(..., description="Unique task identifier")
    description: str = Field(..., description="Task description")
    platform: Platform = Field(..., description="Target platform D")
    mixed_platforms: Optional[List[Platform]] = Field(
        None, description="List of platforms used in mixed-platform tasks"
    )
    topology: TopologySpecification = Field(..., description="Network topology T")
    intent: IntentSpecification = Field(..., description="Intent specification P")
    preconfiguration: Optional[List[PreconfigurationStep]] = Field(
        None, description="Steps to establish initial state"
    )
    fault_verification: Optional[List[Property]] = Field(
        None, description="Properties that MUST be satisfied for the fault to exist"
    )
    convergence: ConvergenceConfig = Field(
        default_factory=ConvergenceConfig,
        description="Convergence configuration",
    )
    optimal_solution: Optional[OptimalSolution] = Field(
        None, description="Optimal solution for efficiency scoring"
    )

    model_config = {"use_enum_values": True}

