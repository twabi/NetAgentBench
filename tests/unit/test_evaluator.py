"""
Unit tests for Evaluator components.

These tests use mocked dependencies for fast execution.
"""
import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from benchmark.models.task import (
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


@pytest.mark.skipif(JsonParser is None, reason="JsonParser not implemented yet")
class TestJsonParser:
    """Unit tests for JsonParser"""

    def test_parse_simple_json(self):
        """Test parsing simple JSON output"""
        parser = JsonParser()
        output = '{"status": "up", "count": 42}'
        success_condition = {
            "json_path": "$.status",
            "expected_value": "up"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True
        assert parsed is not None
        assert parsed.get("status") == "up"

    def test_parse_json_value_mismatch(self):
        """Test when JSON value doesn't match expected"""
        parser = JsonParser()
        output = '{"status": "down"}'
        success_condition = {
            "json_path": "$.status",
            "expected_value": "up"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is False
        assert parsed is not None

    def test_parse_nested_json_path(self):
        """Test parsing nested JSON with jsonpath"""
        parser = JsonParser()
        output = '{"bgp": {"neighbors": [{"state": "established", "ip": "192.0.2.1"}]}}'
        success_condition = {
            "json_path": "$.bgp.neighbors[0].state",
            "expected_value": "established"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_json_check_exists(self):
        """Test checking if a path exists in JSON"""
        parser = JsonParser()
        output = '{"routes": [{"destination": "10.0.0.0/8"}]}'
        success_condition = {
            "json_path": "$.routes[0].destination",
            "exists": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_json_path_not_exists(self):
        """Test when JSON path doesn't exist"""
        parser = JsonParser()
        output = '{"routes": []}'
        success_condition = {
            "json_path": "$.routes[0].destination",
            "exists": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is False

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON"""
        parser = JsonParser()
        output = "not valid json"
        success_condition = {
            "json_path": "$.status",
            "expected_value": "up"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is False
        assert parsed is None

    def test_parse_json_array_length(self):
        """Test checking array length in JSON"""
        parser = JsonParser()
        output = '{"neighbors": [{"id": 1}, {"id": 2}, {"id": 3}]}'
        success_condition = {
            "json_path": "$.neighbors",
            "min_length": 2
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_json_numeric_comparison(self):
        """Test numeric value comparison"""
        parser = JsonParser()
        output = '{"metric": 100}'
        success_condition = {
            "json_path": "$.metric",
            "expected_value": 100
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True


@pytest.mark.skipif(RegexParser is None, reason="RegexParser not implemented yet")
class TestRegexParser:
    """Unit tests for RegexParser"""

    def test_parse_simple_pattern_match(self):
        """Test simple regex pattern matching"""
        parser = RegexParser()
        output = "BGP state = Established"
        success_condition = {
            "pattern": r"state\s*=\s*Established",
            "must_match": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True
        assert parsed is not None
        assert "matched" in parsed

    def test_parse_pattern_no_match(self):
        """Test when pattern doesn't match"""
        parser = RegexParser()
        output = "BGP state = Idle"
        success_condition = {
            "pattern": r"state\s*=\s*Established",
            "must_match": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is False

    def test_parse_with_capture_groups(self):
        """Test pattern with capture groups"""
        parser = RegexParser()
        output = "Neighbor 192.0.2.1 is up"
        success_condition = {
            "pattern": r"Neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+is\s+(\w+)",
            "must_match": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True
        assert parsed is not None
        # Should capture the groups
        if "groups" in parsed:
            assert "192.0.2.1" in parsed["groups"]
            assert "up" in parsed["groups"]

    def test_parse_multiline_pattern(self):
        """Test pattern matching across multiple lines"""
        parser = RegexParser()
        output = """Interface eth0
Status: up
Speed: 1000Mbps"""
        success_condition = {
            "pattern": r"Interface eth0.*Status: up",
            "must_match": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_must_not_match(self):
        """Test pattern that must NOT match"""
        parser = RegexParser()
        output = "No problems detected"
        success_condition = {
            "pattern": r"error|Error|ERROR",
            "must_match": False
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_must_not_match_fails(self):
        """Test must_not_match when pattern is found"""
        parser = RegexParser()
        output = "Error: Connection failed"
        success_condition = {
            "pattern": r"error|Error|ERROR",
            "must_match": False
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is False

    def test_parse_case_insensitive(self):
        """Test case-insensitive matching"""
        parser = RegexParser()
        output = "STATUS: ESTABLISHED"
        success_condition = {
            "pattern": r"status:\s*established",
            "must_match": True,
            "case_insensitive": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True


@pytest.mark.skipif(TextParser is None, reason="TextParser not implemented yet")
class TestTextParser:
    """Unit tests for TextParser"""

    def test_parse_contains_text(self):
        """Test simple text contains"""
        parser = TextParser()
        output = "Interface eth0 is up and running"
        success_condition = {
            "contains_text": "is up"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_not_contains(self):
        """Test when text is not found"""
        parser = TextParser()
        output = "Interface eth0 is down"
        success_condition = {
            "contains_text": "is up"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is False

    def test_parse_case_sensitive(self):
        """Test case-sensitive text matching"""
        parser = TextParser()
        output = "Status: UP"
        success_condition = {
            "contains_text": "up"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        # By default, should be case-sensitive
        assert satisfied is False

    def test_parse_case_insensitive(self):
        """Test case-insensitive text matching"""
        parser = TextParser()
        output = "Status: UP"
        success_condition = {
            "contains_text": "up",
            "case_insensitive": True
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_multiple_contains_all(self):
        """Test multiple strings all must be present"""
        parser = TextParser()
        output = "BGP session established with peer 192.0.2.1"
        success_condition = {
            "contains_all": ["BGP", "established", "192.0.2.1"]
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_contains_any(self):
        """Test any of the strings must be present"""
        parser = TextParser()
        output = "Connection established"
        success_condition = {
            "contains_any": ["error", "failed", "established"]
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is True

    def test_parse_empty_output(self):
        """Test parsing empty output"""
        parser = TextParser()
        output = ""
        success_condition = {
            "contains_text": "something"
        }
        
        satisfied, parsed = parser.parse(output, success_condition)
        
        assert satisfied is False


@pytest.mark.skipif(ParserRegistry is None, reason="ParserRegistry not implemented yet")
class TestParserRegistry:
    """Unit tests for ParserRegistry"""

    def test_get_parser_json(self):
        """Test getting JSON parser from registry"""
        registry = ParserRegistry()
        parser = registry.get_parser("json")
        
        assert isinstance(parser, JsonParser)

    def test_get_parser_regex(self):
        """Test getting regex parser from registry"""
        registry = ParserRegistry()
        parser = registry.get_parser("regex")
        
        assert isinstance(parser, RegexParser)

    def test_get_parser_text(self):
        """Test getting text parser from registry"""
        registry = ParserRegistry()
        parser = registry.get_parser("text")
        
        assert isinstance(parser, TextParser)

    def test_get_parser_unknown(self):
        """Test getting unknown parser type"""
        registry = ParserRegistry()
        
        with pytest.raises(ValueError):
            registry.get_parser("unknown")

    def test_get_parser_case_insensitive(self):
        """Test parser name lookup is case-insensitive"""
        registry = ParserRegistry()
        parser = registry.get_parser("JSON")
        
        assert isinstance(parser, JsonParser)


@pytest.mark.skipif(PropertyEvaluator is None, reason="PropertyEvaluator not implemented yet")
class TestPropertyEvaluator:
    """Unit tests for PropertyEvaluator with mocked observations"""

    def test_evaluate_property_success(self):
        """Test successful property evaluation"""
        # Mock infrastructure
        mock_infrastructure = Mock()
        
        # Create property with text parser
        prop = Property(
            id="test_prop",
            type=PropertyType.REACHABILITY,
            description="Test property",
            evaluation=EvaluationProcedure(
                method="exec_and_parse",
                target_node="test_node",
                command="echo test",
                parser="text",
                success_condition={"contains_text": "test"}
            )
        )
        
        # Mock ObservationExecutor - must be done before creating PropertyEvaluator
        with patch('benchmark.evaluator.property.ObservationExecutor') as mock_obs_class:
            mock_obs = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.raw_output = "test output"
            mock_result.stderr = ""
            mock_result.execution_time = 0.1
            mock_result.exit_code = 0
            mock_result.error = None
            mock_obs.observe.return_value = mock_result
            mock_obs_class.return_value = mock_obs
            
            # Create evaluator after mocking
            evaluator = PropertyEvaluator()
            result = evaluator.evaluate_property(mock_infrastructure, "topo_123", prop)
            
            # Verify result
            assert isinstance(result, PropertyEvaluationResult)
            assert result.property_id == "test_prop"
            assert result.satisfied is True
            assert result.observation_raw == "test output"
            assert result.evaluation_time_seconds >= 0

    def test_evaluate_property_failure(self):
        """Test property evaluation when condition fails"""
        evaluator = PropertyEvaluator()
        
        mock_infrastructure = Mock()
        
        prop = Property(
            id="fail_prop",
            type=PropertyType.REACHABILITY,
            description="Failing property",
            evaluation=EvaluationProcedure(
                method="exec_and_parse",
                target_node="test_node",
                command="echo wrong",
                parser="text",
                success_condition={"contains_text": "correct"}
            )
        )
        
        with patch('benchmark.evaluator.property.ObservationExecutor') as mock_obs_class:
            mock_obs = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.raw_output = "wrong output"
            mock_result.stderr = ""
            mock_result.execution_time = 0.1
            mock_result.exit_code = 0
            mock_result.error = None
            mock_obs.observe.return_value = mock_result
            mock_obs_class.return_value = mock_obs
            
            result = evaluator.evaluate_property(mock_infrastructure, "topo_123", prop)
            
            assert result.satisfied is False

    def test_evaluate_property_observation_fails(self):
        """Test property evaluation when observation command fails"""
        evaluator = PropertyEvaluator()
        
        mock_infrastructure = Mock()
        
        prop = Property(
            id="obs_fail",
            type=PropertyType.REACHABILITY,
            description="Observation fails",
            evaluation=EvaluationProcedure(
                method="exec_and_parse",
                target_node="test_node",
                command="failing_command",
                parser="text",
                success_condition={"contains_text": "test"}
            )
        )
        
        with patch('benchmark.evaluator.property.ObservationExecutor') as mock_obs_class:
            mock_obs = Mock()
            mock_result = Mock()
            mock_result.success = False
            mock_result.raw_output = ""
            mock_result.stderr = "error"
            mock_result.execution_time = 0.1
            mock_result.exit_code = 1
            mock_result.error = "Command failed"
            mock_obs.observe.return_value = mock_result
            mock_obs_class.return_value = mock_obs
            
            result = evaluator.evaluate_property(mock_infrastructure, "topo_123", prop)
            
            # Should handle gracefully
            assert isinstance(result, PropertyEvaluationResult)
            assert result.satisfied is False
            assert result.error_message is not None

    def test_evaluate_property_with_json_parser(self):
        """Test property evaluation with JSON parser"""
        mock_infrastructure = Mock()
        
        prop = Property(
            id="json_prop",
            type=PropertyType.BGP_CONFIGURATION,
            description="JSON property",
            evaluation=EvaluationProcedure(
                method="exec_and_parse",
                target_node="test_node",
                command="show bgp json",
                parser="json",
                success_condition={"json_path": "$.state", "expected_value": "up"}
            )
        )
        
        with patch('benchmark.evaluator.property.ObservationExecutor') as mock_obs_class:
            mock_obs = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.raw_output = '{"state": "up", "peers": 3}'
            mock_result.stderr = ""
            mock_result.execution_time = 0.2
            mock_result.exit_code = 0
            mock_result.error = None
            mock_obs.observe.return_value = mock_result
            mock_obs_class.return_value = mock_obs
            
            evaluator = PropertyEvaluator()
            result = evaluator.evaluate_property(mock_infrastructure, "topo_123", prop)
            
            assert result.satisfied is True
            assert result.observation_parsed is not None
            assert result.observation_parsed.get("state") == "up"

    def test_evaluate_all_properties(self):
        """Test evaluating multiple properties"""
        evaluator = PropertyEvaluator()
        
        mock_infrastructure = Mock()
        
        properties = [
            Property(
                id="prop1",
                type=PropertyType.REACHABILITY,
                description="Property 1",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="node1",
                    command="echo test1",
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
                    target_node="node2",
                    command="echo test2",
                    parser="text",
                    success_condition={"contains_text": "test2"}
                )
            ),
        ]
        
        with patch('benchmark.evaluator.property.ObservationExecutor') as mock_obs_class:
            mock_obs = Mock()
            # Mock returns matching output
            def mock_observe(infra, topo_id, eval_proc):
                mock_result = Mock()
                mock_result.success = True
                mock_result.raw_output = eval_proc.command  # Echo returns the command
                mock_result.stderr = ""
                mock_result.execution_time = 0.1
                mock_result.exit_code = 0
                mock_result.error = None
                return mock_result
            
            mock_obs.observe.side_effect = mock_observe
            mock_obs_class.return_value = mock_obs
            
            results = evaluator.evaluate_all_properties(
                mock_infrastructure, 
                "topo_123", 
                properties
            )
            
            assert len(results) == 2
            assert all(isinstance(r, PropertyEvaluationResult) for r in results)
            assert results[0].property_id == "prop1"
            assert results[1].property_id == "prop2"

    def test_evaluate_all_continues_on_failure(self):
        """Test that evaluation continues even when properties fail"""
        mock_infrastructure = Mock()
        
        properties = [
            Property(
                id="success",
                type=PropertyType.REACHABILITY,
                description="Success",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="node1",
                    command="echo success",
                    parser="text",
                    success_condition={"contains_text": "success"}
                )
            ),
            Property(
                id="failure",
                type=PropertyType.REACHABILITY,
                description="Failure",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="node1",
                    command="echo wrong",
                    parser="text",
                    success_condition={"contains_text": "correct"}
                )
            ),
            Property(
                id="another_success",
                type=PropertyType.REACHABILITY,
                description="Another success",
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="node1",
                    command="echo works",
                    parser="text",
                    success_condition={"contains_text": "works"}
                )
            ),
        ]
        
        with patch('benchmark.evaluator.property.ObservationExecutor') as mock_obs_class:
            mock_obs = Mock()
            
            def mock_observe(infra, topo_id, eval_proc):
                mock_result = Mock()
                mock_result.success = True
                mock_result.raw_output = eval_proc.command
                mock_result.stderr = ""
                mock_result.execution_time = 0.1
                mock_result.exit_code = 0
                mock_result.error = None
                return mock_result
            
            mock_obs.observe.side_effect = mock_observe
            mock_obs_class.return_value = mock_obs
            
            evaluator = PropertyEvaluator()
            results = evaluator.evaluate_all_properties(
                mock_infrastructure,
                "topo_123",
                properties
            )
            
            # All three should be evaluated
            assert len(results) == 3
            assert results[0].satisfied is True
            assert results[1].satisfied is False
            assert results[2].satisfied is True

    def test_evaluate_handles_parsing_exception(self):
        """Test that evaluation handles parsing exceptions gracefully"""
        evaluator = PropertyEvaluator()
        
        mock_infrastructure = Mock()
        
        prop = Property(
            id="parse_error",
            type=PropertyType.BGP_CONFIGURATION,
            description="Causes parse error",
            evaluation=EvaluationProcedure(
                method="exec_and_parse",
                target_node="test_node",
                command="echo bad",
                parser="json",
                success_condition={"json_path": "$.state", "expected_value": "up"}
            )
        )
        
        with patch('benchmark.evaluator.property.ObservationExecutor') as mock_obs_class:
            mock_obs = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.raw_output = "not valid json"
            mock_result.stderr = ""
            mock_result.execution_time = 0.1
            mock_result.exit_code = 0
            mock_result.error = None
            mock_obs.observe.return_value = mock_result
            mock_obs_class.return_value = mock_obs
            
            result = evaluator.evaluate_property(mock_infrastructure, "topo_123", prop)
            
            # Should not crash, should indicate failure
            assert isinstance(result, PropertyEvaluationResult)
            assert result.satisfied is False
            assert result.error_message is not None

