"""
Unit tests for TaskPresenter.

Tests task presentation in various human-readable formats.
"""
import pytest
import json
from benchmark.presenter import TaskPresenter
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


class TestTaskPresenter:
    """Test TaskPresenter class."""

    def create_simple_task(self) -> TaskDefinition:
        """Create a simple 2-node reachability task for testing."""
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
            task_id="reachability_2node_test",
            description="Test reachability between two routers",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

    def test_create_presenter(self):
        """Test creating a TaskPresenter instance."""
        presenter = TaskPresenter()
        assert presenter is not None

    def test_present_task_text_contains_key_info(self):
        """Test that text presentation contains key task information."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        text = presenter.present_task_text(task)

        # Check for key elements
        assert "reachability_2node_test" in text
        assert "Test reachability between two routers" in text
        assert "R1" in text
        assert "R2" in text
        assert "frr" in text.lower()
        assert "reachability" in text.lower()

    def test_present_task_text_shows_topology(self):
        """Test that text presentation shows topology details."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        text = presenter.present_task_text(task)

        # Should show nodes
        assert "Nodes:" in text or "nodes" in text.lower()
        # Should show links
        assert "Link" in text or "link" in text.lower()
        assert "R1:eth1" in text or "eth1" in text

    def test_present_task_text_shows_properties(self):
        """Test that text presentation shows properties to verify."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        text = presenter.present_task_text(task)

        # Should show properties/requirements
        assert "R1 can ping R2" in text or "reachability" in text.lower()

    def test_present_task_markdown_contains_headers(self):
        """Test that markdown presentation has proper markdown headers."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        markdown = presenter.present_task_markdown(task)

        # Should have markdown headers
        assert "# " in markdown or "## " in markdown
        # Check for key sections
        assert "Task" in markdown or "task" in markdown.lower()
        assert "Topology" in markdown or "topology" in markdown.lower()

    def test_present_task_markdown_has_code_blocks(self):
        """Test that markdown presentation uses code blocks for technical info."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        markdown = presenter.present_task_markdown(task)

        # Should have code blocks for commands or examples
        # Either ``` or `
        assert "`" in markdown

    def test_present_task_json_valid_json(self):
        """Test that JSON presentation is valid JSON."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        json_str = presenter.present_task_json(task)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "task_id" in parsed
        assert parsed["task_id"] == "reachability_2node_test"

    def test_present_task_json_pretty_formatted(self):
        """Test that JSON presentation is pretty-printed."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        json_str = presenter.present_task_json(task)

        # Pretty-printed JSON should have newlines and indentation
        assert "\n" in json_str
        assert "  " in json_str or "\t" in json_str

    def test_present_task_json_contains_all_fields(self):
        """Test that JSON presentation includes all task fields."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        json_str = presenter.present_task_json(task)
        parsed = json.loads(json_str)

        # Check for required fields
        assert "task_id" in parsed
        assert "description" in parsed
        assert "platform" in parsed
        assert "topology" in parsed
        assert "intent" in parsed

    def test_present_task_with_complex_topology(self):
        """Test presenting a task with a more complex topology."""
        # Create a 3-node task
        topology = TopologySpecification(
            nodes=[
                Node(
                    name=f"R{i}",
                    type=NodeType.ROUTER,
                    image="frrouting/frr:latest",
                    platform=Platform.FRR,
                )
                for i in range(1, 4)
            ],
            links=[
                Link(endpoints=["R1:eth1", "R2:eth1"]),
                Link(endpoints=["R2:eth2", "R3:eth1"]),
            ],
        )

        intent = IntentSpecification(
            properties=[
                Property(
                    id="reach_R1_to_R3",
                    type="reachability",
                    description="R1 can reach R3",
                    evaluation=EvaluationProcedure(
                        method="exec_and_parse",
                        target_node="R1",
                        command="ping -c 3 10.0.0.3",
                        parser="text",
                        success_condition={"contains_text": "3 packets received"},
                    ),
                )
            ]
        )

        task = TaskDefinition(
            task_id="reachability_3node",
            description="Three-node reachability",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        presenter = TaskPresenter()
        text = presenter.present_task_text(task)

        # Should mention all nodes
        assert "R1" in text
        assert "R2" in text
        assert "R3" in text

    def test_text_presentation_is_readable(self):
        """Test that text presentation is human-readable (not just JSON dump)."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        text = presenter.present_task_text(task)

        # Should NOT be JSON (no opening brace at start)
        assert not text.strip().startswith("{")
        # Should have some structure (newlines, sections)
        assert "\n" in text
        # Should be readable (has spaces between words)
        assert "  " in text or ": " in text

    def test_different_formats_contain_same_info(self):
        """Test that different formats contain the same core information."""
        presenter = TaskPresenter()
        task = self.create_simple_task()

        text = presenter.present_task_text(task)
        markdown = presenter.present_task_markdown(task)
        json_str = presenter.present_task_json(task)

        # All should contain task ID
        assert task.task_id in text
        assert task.task_id in markdown
        assert task.task_id in json_str

        # All should contain node names
        assert "R1" in text and "R2" in text
        assert "R1" in markdown and "R2" in markdown
        assert "R1" in json_str and "R2" in json_str

