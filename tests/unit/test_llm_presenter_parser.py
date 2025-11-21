"""
Unit tests for LLM task presenter and response parser.

Tests formatting tasks for LLM consumption and parsing LLM responses.
"""
import pytest
import json
from benchmark.llm.presenter import LLMTaskPresenter
from benchmark.llm.parser import LLMResponseParser
from benchmark.models.task import (
    TaskDefinition,
    TopologySpecification,
    Node,
    Link,
    IntentSpecification,
    Property,
    EvaluationProcedure,
    Platform,
    NodeType,
)
from benchmark.models.submission import Submission


class TestLLMTaskPresenter:
    """Test LLMTaskPresenter for formatting tasks for LLMs."""

    def create_simple_task(self) -> TaskDefinition:
        """Create a simple task for testing."""
        topology = TopologySpecification(
            nodes=[
                Node(
                    name="R1",
                    type=NodeType.ROUTER,
                    image="frrouting/frr:latest",
                    platform=Platform.FRR,
                ),
                Node(
                    name="R2",
                    type=NodeType.ROUTER,
                    image="frrouting/frr:latest",
                    platform=Platform.FRR,
                ),
            ],
            links=[Link(endpoints=["R1:eth1", "R2:eth1"])],
        )

        intent = IntentSpecification(
            properties=[
                Property(
                    id="reach_R1_to_R2",
                    type="reachability",
                    description="R1 can ping R2",
                    evaluation=EvaluationProcedure(
                        method="exec_and_parse",
                        target_node="R1",
                        command="ping -c 3 10.0.0.2",
                        parser="text",
                        success_condition={"contains_text": "3 packets received"},
                    ),
                )
            ]
        )

        return TaskDefinition(
            task_id="reachability_2node",
            description="Configure two routers for reachability",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

    def test_create_presenter(self):
        """Test creating an LLMTaskPresenter."""
        presenter = LLMTaskPresenter()
        assert presenter is not None

    def test_format_task_for_llm(self):
        """Test formatting a task for LLM."""
        presenter = LLMTaskPresenter()
        task = self.create_simple_task()

        prompt = presenter.format_task_for_llm(task)

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_task_info(self):
        """Test that prompt contains essential task information."""
        presenter = LLMTaskPresenter()
        task = self.create_simple_task()

        prompt = presenter.format_task_for_llm(task)

        # Should contain task ID and description
        assert task.task_id in prompt
        assert task.description in prompt

    def test_prompt_contains_topology(self):
        """Test that prompt describes the topology."""
        presenter = LLMTaskPresenter()
        task = self.create_simple_task()

        prompt = presenter.format_task_for_llm(task)

        # Should mention nodes
        assert "R1" in prompt
        assert "R2" in prompt
        # Should mention topology structure
        assert "topology" in prompt.lower() or "network" in prompt.lower()

    def test_prompt_contains_success_criteria(self):
        """Test that prompt includes success criteria."""
        presenter = LLMTaskPresenter()
        task = self.create_simple_task()

        prompt = presenter.format_task_for_llm(task)

        # Should mention properties/requirements
        assert "R1 can ping R2" in prompt or "reachability" in prompt.lower()

    def test_prompt_contains_response_format(self):
        """Test that prompt includes expected response format."""
        presenter = LLMTaskPresenter()
        task = self.create_simple_task()

        prompt = presenter.format_task_for_llm(task)

        # Should include JSON format instructions
        assert "json" in prompt.lower()
        assert "approach" in prompt.lower()
        assert "commands" in prompt.lower()

    def test_prompt_with_task_context(self):
        """Test formatting with task index context."""
        presenter = LLMTaskPresenter()
        task = self.create_simple_task()

        prompt = presenter.format_task_for_llm(task, task_index=5, total_tasks=10)

        # Should include task progress
        assert "5" in prompt
        assert "10" in prompt


class TestLLMResponseParser:
    """Test LLMResponseParser for parsing LLM responses."""

    def test_create_parser(self):
        """Test creating an LLMResponseParser."""
        parser = LLMResponseParser()
        assert parser is not None

    def test_parse_clean_json(self):
        """Test parsing clean JSON response."""
        parser = LLMResponseParser()

        response = """{
  "approach": {
    "description": "Configure IP addresses",
    "commands": [
      {
        "node": "R1",
        "commands": ["ip addr add 10.0.0.1/24 dev eth1"]
      },
      {
        "node": "R2",
        "commands": ["ip addr add 10.0.0.2/24 dev eth1"]
      }
    ]
  }
}"""

        submission = parser.parse_response(response, task_id="test_task", testee_id="gpt4")

        assert isinstance(submission, Submission)
        assert submission.task_id == "test_task"
        assert submission.testee_id == "gpt4"
        assert submission.testee_type == "llm"
        assert len(submission.approach.commands) == 2

    def test_parse_json_with_markdown_fences(self):
        """Test parsing JSON wrapped in markdown code fences."""
        parser = LLMResponseParser()

        response = """Here's the configuration:

```json
{
  "approach": {
    "description": "Basic setup",
    "commands": [
      {
        "node": "R1",
        "commands": ["echo test"]
      }
    ]
  }
}
```

This should work!"""

        submission = parser.parse_response(response, task_id="test_task", testee_id="claude")

        assert isinstance(submission, Submission)
        assert len(submission.approach.commands) == 1
        assert submission.approach.commands[0].node == "R1"

    def test_parse_json_without_language_tag(self):
        """Test parsing JSON in code fences without language tag."""
        parser = LLMResponseParser()

        response = """```
{
  "approach": {
    "description": "Config",
    "commands": [{"node": "R1", "commands": ["test"]}]
  }
}
```"""

        submission = parser.parse_response(response, task_id="test_task", testee_id="llm")

        assert isinstance(submission, Submission)
        assert len(submission.approach.commands) == 1

    def test_parse_response_with_extra_text(self):
        """Test parsing when LLM includes explanation text."""
        parser = LLMResponseParser()

        response = """Let me help you configure the network. First, we need to set up the interfaces.

{
  "approach": {
    "description": "Interface configuration",
    "commands": [{"node": "R1", "commands": ["ip link set eth1 up"]}]
  }
}

This configuration will enable connectivity."""

        submission = parser.parse_response(response, task_id="test_task", testee_id="llm")

        assert isinstance(submission, Submission)
        assert "Interface configuration" in submission.approach.description

    def test_parse_invalid_json(self):
        """Test error handling for invalid JSON."""
        parser = LLMResponseParser()

        response = "This is not JSON at all!"

        with pytest.raises(ValueError, match="Could not parse"):
            parser.parse_response(response, task_id="test_task", testee_id="llm")

    def test_parse_json_missing_approach(self):
        """Test error handling when approach key is missing."""
        parser = LLMResponseParser()

        response = '{"something": "else"}'

        with pytest.raises(ValueError, match="approach"):
            parser.parse_response(response, task_id="test_task", testee_id="llm")

    def test_parse_multiple_json_blocks(self):
        """Test parsing when response has multiple JSON blocks (uses first)."""
        parser = LLMResponseParser()

        response = """First attempt:
```json
{"approach": {"description": "First", "commands": [{"node": "R1", "commands": ["cmd1"]}]}}
```

Actually, let me fix that:
```json
{"approach": {"description": "Second", "commands": [{"node": "R2", "commands": ["cmd2"]}]}}
```"""

        submission = parser.parse_response(response, task_id="test_task", testee_id="llm")

        # Should use the first valid JSON block
        assert isinstance(submission, Submission)
        assert submission.approach.description == "First"

    def test_extract_json_from_text(self):
        """Test the JSON extraction helper method."""
        parser = LLMResponseParser()

        text = """Some text before
{
  "key": "value",
  "nested": {
    "data": 123
  }
}
Some text after"""

        extracted = parser._extract_json_from_text(text)

        assert extracted is not None
        parsed = json.loads(extracted)
        assert parsed["key"] == "value"
        assert parsed["nested"]["data"] == 123

    def test_parse_sets_testee_type_to_llm(self):
        """Test that parsed submissions always have testee_type='llm'."""
        parser = LLMResponseParser()

        response = '{"approach": {"description": "Test", "commands": [{"node": "R1", "commands": ["test"]}]}}'

        submission = parser.parse_response(response, task_id="task", testee_id="gpt4")

        assert submission.testee_type == "llm"

