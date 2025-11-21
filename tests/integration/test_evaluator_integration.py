"""
Integration tests for Evaluator components.

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
import json

from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.models.task import (
    Node,
    NodeType,
    Platform,
    Link,
    TopologySpecification,
    EvaluationProcedure,
    Property,
    PropertyType,
)

# Import evaluator components (will fail until implemented)
try:
    from benchmark.evaluator.parsers import (
        OutputParser,
        JsonParser,
        RegexParser,
        TextParser,
        ParserRegistry,
    )
    from benchmark.evaluator.property import PropertyEvaluator
    from benchmark.models.results import PropertyEvaluationResult
except ImportError:
    OutputParser = None
    JsonParser = None
    RegexParser = None
    TextParser = None
    ParserRegistry = None
    PropertyEvaluator = None
    PropertyEvaluationResult = None


@pytest.fixture
def simple_topology():
    """Create a simple single-node topology for testing"""
    nodes = [
        Node(
            name="test_node",
            type=NodeType.LINUX,
            image="alpine:latest",
            platform=Platform.FRR,
        )
    ]
    return TopologySpecification(nodes=nodes, links=[])


@pytest.fixture
def provisioned_topology(simple_topology):
    """Provision a topology and return (provider, topology_id)"""
    provider = ContainerlabProvider()
    topology_id = provider.provision(simple_topology)
    
    # Wait for ready
    max_wait = 30
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if provider.is_ready(topology_id):
            break
        time.sleep(2)
    
    yield provider, topology_id
    
    # Cleanup
    provider.teardown(topology_id)


def check_prerequisites():
    """Check if containerlab and docker are available"""
    import subprocess
    try:
        # Check containerlab
        result = subprocess.run(
            ["clab", "version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["sudo", "-n", "clab", "version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False
        
        # Check Docker
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not check_prerequisites(),
    reason="Containerlab or Docker not available",
)


@pytest.mark.integration
@pytest.mark.skipif(JsonParser is None, reason="JsonParser not implemented yet")
class TestJsonParserIntegration:
    """Test JSON parsing with real command output"""

    def test_parse_simple_json_output(self, provisioned_topology):
        """Test parsing JSON from a real command"""
        provider, topology_id = provisioned_topology
        
        # Create a command that outputs JSON
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo \'{"status": "up", "count": 42}\'',
            parser="json",
            success_condition={"json_path": "$.status", "expected_value": "up"}
        )
        
        # Use PropertyEvaluator to get observation and parse
        evaluator = PropertyEvaluator()
        
        # Create a property to evaluate
        prop = Property(
            id="test_json",
            type=PropertyType.REACHABILITY,
            description="Test JSON parsing",
            evaluation=eval_proc
        )
        
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        # Verify result
        assert isinstance(result, PropertyEvaluationResult)
        assert result.satisfied is True
        assert result.observation_parsed is not None
        assert result.observation_parsed.get("status") == "up"

    def test_parse_json_with_nested_path(self, provisioned_topology):
        """Test parsing nested JSON values"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo \'{"bgp": {"neighbors": [{"state": "established", "ip": "192.0.2.1"}]}}\'',
            parser="json",
            success_condition={
                "json_path": "$.bgp.neighbors[0].state",
                "expected_value": "established"
            }
        )
        
        prop = Property(
            id="test_nested",
            type=PropertyType.BGP_CONFIGURATION,
            description="Test nested JSON",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        assert result.satisfied is True

    def test_parse_json_check_existence(self, provisioned_topology):
        """Test checking if a JSON path exists"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo \'{"routes": [{"destination": "10.0.0.0/8"}]}\'',
            parser="json",
            success_condition={
                "json_path": "$.routes[0].destination",
                "exists": True
            }
        )
        
        prop = Property(
            id="test_exists",
            type=PropertyType.ROUTE_EXISTS,
            description="Test path exists",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        assert result.satisfied is True

    def test_parse_invalid_json_handles_gracefully(self, provisioned_topology):
        """Test that invalid JSON is handled gracefully"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo "not valid json"',
            parser="json",
            success_condition={"json_path": "$.status", "expected_value": "up"}
        )
        
        prop = Property(
            id="test_invalid",
            type=PropertyType.REACHABILITY,
            description="Test invalid JSON",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        # Should not crash, but should indicate failure
        assert isinstance(result, PropertyEvaluationResult)
        assert result.satisfied is False
        # Note: Parsing failures don't always set error_message, they just return False


@pytest.mark.integration
@pytest.mark.skipif(RegexParser is None, reason="RegexParser not implemented yet")
class TestRegexParserIntegration:
    """Test regex parsing with real command output"""

    def test_parse_with_simple_pattern(self, provisioned_topology):
        """Test regex matching on real output"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo "BGP state = Established"',
            parser="regex",
            success_condition={
                "pattern": r"state\s*=\s*Established",
                "must_match": True
            }
        )
        
        prop = Property(
            id="test_regex",
            type=PropertyType.BGP_CONFIGURATION,
            description="Test regex",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        assert result.satisfied is True

    def test_regex_pattern_not_found(self, provisioned_topology):
        """Test regex when pattern doesn't match"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo "BGP state = Idle"',
            parser="regex",
            success_condition={
                "pattern": r"state\s*=\s*Established",
                "must_match": True
            }
        )
        
        prop = Property(
            id="test_no_match",
            type=PropertyType.BGP_CONFIGURATION,
            description="Test no match",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        assert result.satisfied is False

    def test_regex_with_capture_groups(self, provisioned_topology):
        """Test regex with capture groups"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo "Neighbor 192.0.2.1 is up"',
            parser="regex",
            success_condition={
                "pattern": r"Neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+is\s+up",
                "must_match": True
            }
        )
        
        prop = Property(
            id="test_capture",
            type=PropertyType.BGP_CONFIGURATION,
            description="Test capture groups",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        assert result.satisfied is True
        # Parsed result should contain match info
        assert result.observation_parsed is not None


@pytest.mark.integration
@pytest.mark.skipif(TextParser is None, reason="TextParser not implemented yet")
class TestTextParserIntegration:
    """Test text parsing with real command output"""

    def test_parse_text_contains(self, provisioned_topology):
        """Test simple text contains check"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo "Interface eth0 is up and running"',
            parser="text",
            success_condition={
                "contains_text": "is up"
            }
        )
        
        prop = Property(
            id="test_text",
            type=PropertyType.INTERFACE_UP,
            description="Test text contains",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        assert result.satisfied is True

    def test_text_not_contains(self, provisioned_topology):
        """Test when text is not found"""
        provider, topology_id = provisioned_topology
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command='echo "Interface eth0 is down"',
            parser="text",
            success_condition={
                "contains_text": "is up"
            }
        )
        
        prop = Property(
            id="test_not_found",
            type=PropertyType.INTERFACE_UP,
            description="Test text not found",
            evaluation=eval_proc
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        assert result.satisfied is False


@pytest.mark.integration
@pytest.mark.skipif(PropertyEvaluator is None, reason="PropertyEvaluator not implemented yet")
class TestPropertyEvaluatorIntegration:
    """Test complete property evaluation workflow"""

    def test_evaluate_single_property_success(self, provisioned_topology):
        """Test evaluating a single property that succeeds"""
        provider, topology_id = provisioned_topology
        
        prop = Property(
            id="ping_test",
            type=PropertyType.REACHABILITY,
            description="Test ping success",
            evaluation=EvaluationProcedure(
                method="exec_and_parse",
                target_node="test_node",
                command='ping -c 1 127.0.0.1',
                parser="text",
                success_condition={"contains_text": "1 packets transmitted"}
            )
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        # Verify result structure
        assert isinstance(result, PropertyEvaluationResult)
        assert result.property_id == "ping_test"
        assert result.satisfied is True
        assert result.observation_raw is not None
        assert result.evaluation_time_seconds >= 0
        assert result.error_message is None

    def test_evaluate_multiple_properties(self, provisioned_topology):
        """Test evaluating multiple properties"""
        provider, topology_id = provisioned_topology
        
        properties = [
            Property(
                id="prop1",
                type=PropertyType.REACHABILITY,
                description="Property 1",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="test_node",
                    command='echo "test1"',
                    parser="text",
                    success_condition={"contains_text": "test1"}
                )
            ),
            Property(
                id="prop2",
                type=PropertyType.REACHABILITY,
                description="Property 2",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="test_node",
                    command='echo "test2"',
                    parser="text",
                    success_condition={"contains_text": "test2"}
                )
            ),
        ]
        
        evaluator = PropertyEvaluator()
        results = evaluator.evaluate_all_properties(provider, topology_id, properties)
        
        assert len(results) == 2
        assert all(isinstance(r, PropertyEvaluationResult) for r in results)
        assert results[0].property_id == "prop1"
        assert results[1].property_id == "prop2"
        assert all(r.satisfied for r in results)

    def test_evaluate_continues_on_failure(self, provisioned_topology):
        """Test that evaluation continues even when a property fails"""
        provider, topology_id = provisioned_topology
        
        properties = [
            Property(
                id="success_prop",
                type=PropertyType.REACHABILITY,
                description="This succeeds",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="test_node",
                    command='echo "success"',
                    parser="text",
                    success_condition={"contains_text": "success"}
                )
            ),
            Property(
                id="fail_prop",
                type=PropertyType.REACHABILITY,
                description="This fails",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="test_node",
                    command='echo "fail"',
                    parser="text",
                    success_condition={"contains_text": "success"}
                )
            ),
            Property(
                id="another_success",
                type=PropertyType.REACHABILITY,
                description="This succeeds too",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="test_node",
                    command='echo "works"',
                    parser="text",
                    success_condition={"contains_text": "works"}
                )
            ),
        ]
        
        evaluator = PropertyEvaluator()
        results = evaluator.evaluate_all_properties(provider, topology_id, properties)
        
        # All three should be evaluated
        assert len(results) == 3
        assert results[0].satisfied is True
        assert results[1].satisfied is False
        assert results[2].satisfied is True

    def test_evaluate_with_command_failure(self, provisioned_topology):
        """Test evaluation when the observation command fails"""
        provider, topology_id = provisioned_topology
        
        prop = Property(
            id="failing_cmd",
            type=PropertyType.REACHABILITY,
            description="Command that fails",
            evaluation=EvaluationProcedure(
                method="exec_and_parse",
                target_node="test_node",
                command='false',  # This command always fails
                parser="text",
                success_condition={"contains_text": "anything"}
            )
        )
        
        evaluator = PropertyEvaluator()
        result = evaluator.evaluate_property(provider, topology_id, prop)
        
        # Should handle gracefully
        assert isinstance(result, PropertyEvaluationResult)
        # Command failure might result in unsatisfied property
        # The evaluator should still return a result, not crash

