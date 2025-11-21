"""
Unit tests for LLMTestee runner.

Tests the LLM testee implementation that uses providers, presenters, and parsers.
"""
import pytest
from benchmark.llm.runner import LLMTestee
from benchmark.llm.providers import MockLLMProvider
from benchmark.models.llm_config import LLMConfig
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


class TestLLMTestee:
    """Test LLMTestee implementation."""

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
            task_id="test_task",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

    def test_create_llm_testee(self):
        """Test creating an LLMTestee."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        testee = LLMTestee(provider=provider, testee_id="gpt4_test")

        assert testee is not None
        assert testee.testee_id == "gpt4_test"
        assert testee.provider == provider

    def test_llm_testee_default_id(self):
        """Test LLMTestee with default ID."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        testee = LLMTestee(provider=provider)

        assert testee.testee_id == "llm_testee"

    def test_llm_testee_generate_submission(self):
        """Test generating a submission via LLM."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        testee = LLMTestee(provider=provider, testee_id="test_llm")
        task = self.create_simple_task()

        submission = testee.generate_submission(task)

        assert submission is not None
        assert submission.task_id == task.task_id
        assert submission.testee_id == "test_llm"
        assert submission.testee_type == "llm"

    def test_llm_testee_calls_provider(self):
        """Test that LLMTestee calls the provider."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        testee = LLMTestee(provider=provider)
        task = self.create_simple_task()

        testee.generate_submission(task)

        # Provider should have been called
        assert provider.call_count == 1
        assert provider.last_prompt is not None

    def test_llm_testee_formats_task_in_prompt(self):
        """Test that task is formatted in the prompt."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        testee = LLMTestee(provider=provider)
        task = self.create_simple_task()

        testee.generate_submission(task)

        # Prompt should contain task information
        prompt = provider.last_prompt
        assert task.task_id in prompt
        assert "R1" in prompt
        assert "R2" in prompt

    def test_llm_testee_parses_response(self):
        """Test that LLM response is parsed correctly."""
        config = LLMConfig(provider="mock", model="mock-model")

        # Set a valid mock response
        mock_response = '''```json
{
  "approach": {
    "description": "Configure interfaces",
    "commands": [
      {"node": "R1", "commands": ["ip addr add 10.0.0.1/24 dev eth1"]},
      {"node": "R2", "commands": ["ip addr add 10.0.0.2/24 dev eth1"]}
    ]
  }
}
```'''
        provider = MockLLMProvider(config, mock_response=mock_response)

        testee = LLMTestee(provider=provider)
        task = self.create_simple_task()

        submission = testee.generate_submission(task)

        # Check that submission was parsed correctly
        assert len(submission.approach.commands) == 2
        assert submission.approach.commands[0].node == "R1"
        assert submission.approach.commands[1].node == "R2"

    def test_llm_testee_get_testee_info(self):
        """Test getting testee info."""
        config = LLMConfig(provider="mock", model="gpt-4-turbo")
        provider = MockLLMProvider(config)

        testee = LLMTestee(provider=provider, testee_id="gpt4_turbo_001")
        info = testee.get_testee_info()

        assert isinstance(info, dict)
        assert info["testee_id"] == "gpt4_turbo_001"
        assert info["testee_type"] == "llm"
        assert info["provider"] == "mock"
        assert info["model"] == "gpt-4-turbo"

    def test_llm_testee_handles_malformed_response(self):
        """Test error handling for malformed LLM response."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(
            config, mock_response="This is not JSON at all!"
        )

        testee = LLMTestee(provider=provider)
        task = self.create_simple_task()

        # Should raise an error
        with pytest.raises(ValueError, match="Could not parse"):
            testee.generate_submission(task)

    def test_llm_testee_with_task_context(self):
        """Test LLMTestee with task context (index/total)."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        testee = LLMTestee(provider=provider)
        task = self.create_simple_task()

        submission = testee.generate_submission(task, task_index=3, total_tasks=10)

        # Provider should have been called with context in prompt
        assert provider.call_count == 1
        prompt = provider.last_prompt
        assert "3" in prompt
        assert "10" in prompt

