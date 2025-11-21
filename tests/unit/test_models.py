"""
Unit tests for Pydantic models.
Following TDD: Write tests first, then implement models.
"""
import pytest
from pydantic import ValidationError


class TestEnums:
    """Test enum definitions"""

    def test_platform_enum_exists(self):
        """Test that Platform enum is defined with expected values"""
        from benchmark.models.task import Platform

        assert Platform.FRR == "frr"
        assert Platform.CISCO_IOS == "cisco_ios"
        assert Platform.JUNIPER_JUNOS == "juniper_junos"
        assert Platform.VYOS == "vyos"

    def test_node_type_enum_exists(self):
        """Test that NodeType enum is defined"""
        from benchmark.models.task import NodeType

        assert NodeType.ROUTER == "router"
        assert NodeType.SWITCH == "switch"
        assert NodeType.HOST == "host"
        assert NodeType.LINUX == "linux"


class TestNodeModel:
    """Test Node model"""

    def test_node_creation_with_all_fields(self):
        """Test creating a node with all fields"""
        from benchmark.models.task import Node, NodeType, Platform

        node = Node(
            name="R1",
            type=NodeType.ROUTER,
            image="frrouting/frr:latest",
            platform=Platform.FRR,
        )

        assert node.name == "R1"
        assert node.type == NodeType.ROUTER
        assert node.image == "frrouting/frr:latest"
        assert node.platform == Platform.FRR

    def test_node_creation_with_defaults(self):
        """Test creating a node with default values"""
        from benchmark.models.task import Node, NodeType, Platform

        node = Node(name="R1", type=NodeType.ROUTER)

        assert node.name == "R1"
        assert node.type == NodeType.ROUTER
        assert node.image == "frrouting/frr:latest"  # Default value
        assert node.platform == Platform.FRR  # Default value

    def test_node_requires_name(self):
        """Test that node requires a name"""
        from benchmark.models.task import Node, NodeType

        with pytest.raises(ValidationError) as exc_info:
            Node(type=NodeType.ROUTER)

        assert "name" in str(exc_info.value)

    def test_node_requires_type(self):
        """Test that node requires a type"""
        from benchmark.models.task import Node

        with pytest.raises(ValidationError) as exc_info:
            Node(name="R1")

        assert "type" in str(exc_info.value)

    def test_node_json_serialization(self):
        """Test that node can be serialized to JSON"""
        from benchmark.models.task import Node, NodeType, Platform

        node = Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR)
        json_str = node.model_dump_json()

        assert '"name":"R1"' in json_str or '"name": "R1"' in json_str
        assert "router" in json_str

    def test_node_json_deserialization(self):
        """Test that node can be deserialized from JSON"""
        from benchmark.models.task import Node

        json_data = {
            "name": "R1",
            "type": "router",
            "image": "frrouting/frr:latest",
            "platform": "frr",
        }

        node = Node(**json_data)
        assert node.name == "R1"


class TestInterfaceModel:
    """Test Interface model"""

    def test_interface_creation_with_all_fields(self):
        """Test creating an interface with all fields"""
        from benchmark.models.task import Interface

        interface = Interface(name="eth1", ip="192.168.1.1/24", mtu=1500)

        assert interface.name == "eth1"
        assert interface.ip == "192.168.1.1/24"
        assert interface.mtu == 1500

    def test_interface_optional_fields(self):
        """Test that IP and MTU are optional"""
        from benchmark.models.task import Interface

        interface = Interface(name="eth1")

        assert interface.name == "eth1"
        assert interface.ip is None
        assert interface.mtu is None


class TestLinkModel:
    """Test Link model"""

    def test_link_creation(self):
        """Test creating a link"""
        from benchmark.models.task import Link

        link = Link(endpoints=["R1:eth1", "R2:eth1"])

        assert len(link.endpoints) == 2
        assert link.endpoints[0] == "R1:eth1"
        assert link.endpoints[1] == "R2:eth1"

    def test_link_requires_endpoints(self):
        """Test that link requires endpoints"""
        from benchmark.models.task import Link

        with pytest.raises(ValidationError):
            Link()


class TestTopologySpecification:
    """Test TopologySpecification model"""

    def test_topology_creation_with_nodes(self):
        """Test creating a topology with nodes"""
        from benchmark.models.task import TopologySpecification, Node, NodeType

        nodes = [
            Node(name="R1", type=NodeType.ROUTER),
            Node(name="R2", type=NodeType.ROUTER),
        ]

        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])

        assert len(topology.nodes) == 2
        assert topology.nodes[0].name == "R1"

    def test_topology_requires_at_least_one_node(self):
        """Test that topology requires at least one node"""
        from benchmark.models.task import TopologySpecification

        with pytest.raises(ValidationError) as exc_info:
            TopologySpecification(nodes=[], links=[], interfaces=[])

        assert "at least 1 item" in str(exc_info.value).lower()

    def test_topology_validates_unique_node_names(self):
        """Test that node names must be unique"""
        from benchmark.models.task import TopologySpecification, Node, NodeType

        nodes = [
            Node(name="R1", type=NodeType.ROUTER),
            Node(name="R1", type=NodeType.ROUTER),  # Duplicate name
        ]

        with pytest.raises(ValidationError) as exc_info:
            TopologySpecification(nodes=nodes, links=[], interfaces=[])

        assert "unique" in str(exc_info.value).lower()

    def test_topology_validates_link_references_existing_nodes(self):
        """Test that links must reference existing nodes"""
        from benchmark.models.task import TopologySpecification, Node, NodeType, Link

        nodes = [
            Node(name="R1", type=NodeType.ROUTER),
            Node(name="R2", type=NodeType.ROUTER),
        ]

        # Link references non-existent node "R3"
        links = [Link(endpoints=["R1:eth1", "R3:eth1"])]

        with pytest.raises(ValidationError) as exc_info:
            TopologySpecification(nodes=nodes, links=links, interfaces=[])

        error_msg = str(exc_info.value).lower()
        assert "unknown node" in error_msg or "r3" in error_msg


class TestEvaluationProcedure:
    """Test EvaluationProcedure model"""

    def test_evaluation_procedure_creation(self):
        """Test creating an evaluation procedure"""
        from benchmark.models.task import EvaluationProcedure

        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="vtysh -c 'show bgp summary json'",
            parser="json",
            success_condition={"json_path": "$.state", "expected_value": "Established"},
        )

        assert eval_proc.method == "exec_and_parse"
        assert eval_proc.target_node == "R1"
        assert eval_proc.parser == "json"


class TestPropertyModel:
    """Test Property model"""

    def test_property_creation(self):
        """Test creating a property"""
        from benchmark.models.task import Property, PropertyType, EvaluationProcedure

        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="ping -c 3 192.168.1.2",
            parser="regex",
            success_condition={"pattern": "3 received", "must_match": True},
        )

        prop = Property(
            id="p1_reachability",
            type=PropertyType.REACHABILITY,
            description="R1 can ping R2",
            evaluation=eval_proc,
        )

        assert prop.id == "p1_reachability"
        assert prop.type == PropertyType.REACHABILITY
        assert prop.description == "R1 can ping R2"


class TestIntentSpecification:
    """Test IntentSpecification model"""

    def test_intent_creation_with_properties(self):
        """Test creating an intent specification"""
        from benchmark.models.task import (
            IntentSpecification,
            Property,
            PropertyType,
            EvaluationProcedure,
        )

        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="ping -c 3 192.168.1.2",
            parser="regex",
            success_condition={"pattern": "3 received"},
        )

        properties = [
            Property(
                id="p1",
                type=PropertyType.REACHABILITY,
                description="Test",
                evaluation=eval_proc,
            )
        ]

        intent = IntentSpecification(properties=properties)

        assert len(intent.properties) == 1
        assert intent.properties[0].id == "p1"

    def test_intent_validates_unique_property_ids(self):
        """Test that property IDs must be unique"""
        from benchmark.models.task import (
            IntentSpecification,
            Property,
            PropertyType,
            EvaluationProcedure,
        )

        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="test",
            parser="text",
            success_condition={},
        )

        properties = [
            Property(
                id="p1", type=PropertyType.REACHABILITY, description="Test 1", evaluation=eval_proc
            ),
            Property(
                id="p1", type=PropertyType.REACHABILITY, description="Test 2", evaluation=eval_proc
            ),  # Duplicate ID
        ]

        with pytest.raises(ValidationError) as exc_info:
            IntentSpecification(properties=properties)

        assert "unique" in str(exc_info.value).lower()


class TestConvergenceConfig:
    """Test ConvergenceConfig model"""

    def test_convergence_config_with_defaults(self):
        """Test convergence config with default values"""
        from benchmark.models.task import ConvergenceConfig

        config = ConvergenceConfig()

        assert config.timeout_seconds == 30
        assert config.check_interval_seconds == 2

    def test_convergence_config_with_custom_values(self):
        """Test convergence config with custom values"""
        from benchmark.models.task import ConvergenceConfig

        config = ConvergenceConfig(timeout_seconds=60, check_interval_seconds=5)

        assert config.timeout_seconds == 60
        assert config.check_interval_seconds == 5


class TestTaskDefinition:
    """Test TaskDefinition model (the main model)"""

    def test_task_definition_creation(self):
        """Test creating a complete task definition"""
        from benchmark.models.task import (
            TaskDefinition,
            Platform,
            TopologySpecification,
            Node,
            NodeType,
            IntentSpecification,
            Property,
            PropertyType,
            EvaluationProcedure,
            ConvergenceConfig,
        )

        # Create topology
        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])

        # Create intent
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="test",
            parser="text",
            success_condition={},
        )
        properties = [
            Property(id="p1", type=PropertyType.INTERFACE_UP, description="Test", evaluation=eval_proc)
        ]
        intent = IntentSpecification(properties=properties)

        # Create task
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
            convergence=ConvergenceConfig(),
        )

        assert task.task_id == "test_001"
        assert task.platform == Platform.FRR
        assert len(task.topology.nodes) == 1
        assert len(task.intent.properties) == 1

    def test_task_definition_json_round_trip(self):
        """Test that task can be serialized and deserialized"""
        from benchmark.models.task import (
            TaskDefinition,
            Platform,
            TopologySpecification,
            Node,
            NodeType,
            IntentSpecification,
            Property,
            PropertyType,
            EvaluationProcedure,
        )

        # Create minimal task
        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])

        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="test",
            parser="text",
            success_condition={},
        )
        properties = [
            Property(id="p1", type=PropertyType.INTERFACE_UP, description="Test", evaluation=eval_proc)
        ]
        intent = IntentSpecification(properties=properties)

        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        # Serialize to JSON
        json_str = task.model_dump_json()

        # Deserialize from JSON
        import json

        json_dict = json.loads(json_str)
        task_restored = TaskDefinition(**json_dict)

        assert task_restored.task_id == task.task_id
        assert task_restored.platform == task.platform

