"""
Unit tests for testee interfaces and implementations.

Tests BaseTestee, HumanJsonTestee, and BaselineTestee.
"""
import pytest
import json
import tempfile
from pathlib import Path
from benchmark.testee.base import BaseTestee
from benchmark.testee.human import HumanJsonTestee
from benchmark.testee.baseline import BaselineTestee
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


class TestBaseTestee:
    """Test BaseTestee abstract interface."""

    def test_base_testee_is_abstract(self):
        """Test that BaseTestee cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseTestee()

    def test_base_testee_requires_generate_submission(self):
        """Test that subclasses must implement generate_submission."""

        class IncompleteTestee(BaseTestee):
            def get_testee_info(self):
                return {}

        with pytest.raises(TypeError):
            IncompleteTestee()

    def test_base_testee_requires_get_testee_info(self):
        """Test that subclasses must implement get_testee_info."""

        class IncompleteTestee(BaseTestee):
            def generate_submission(self, task):
                return None

        with pytest.raises(TypeError):
            IncompleteTestee()


class TestBaselineTestee:
    """Test BaselineTestee implementation."""

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

    def test_create_baseline_testee(self):
        """Test creating a BaselineTestee."""
        testee = BaselineTestee(testee_id="baseline_001")
        assert testee is not None
        assert testee.testee_id == "baseline_001"

    def test_baseline_testee_default_id(self):
        """Test BaselineTestee with default ID."""
        testee = BaselineTestee()
        assert testee.testee_id == "baseline"

    def test_baseline_generate_submission(self):
        """Test that BaselineTestee generates a valid submission."""
        testee = BaselineTestee(testee_id="baseline_test")
        task = self.create_simple_task()

        submission = testee.generate_submission(task)

        assert isinstance(submission, Submission)
        assert submission.task_id == task.task_id
        assert submission.testee_id == "baseline_test"
        assert submission.testee_type == "baseline"

    def test_baseline_submission_has_empty_commands(self):
        """Test that baseline generates minimal commands."""
        testee = BaselineTestee()
        task = self.create_simple_task()

        submission = testee.generate_submission(task)

        # Baseline should have command sequences for all nodes
        assert len(submission.approach.commands) == len(task.topology.nodes)

        # Commands should be minimal (just baseline comments)
        for cmd_seq in submission.approach.commands:
            assert len(cmd_seq.commands) >= 1
            # Should contain minimal/no-op commands
            assert all("#" in cmd or cmd == "" for cmd in cmd_seq.commands)

    def test_baseline_get_testee_info(self):
        """Test getting testee info from BaselineTestee."""
        testee = BaselineTestee(testee_id="baseline_xyz")
        info = testee.get_testee_info()

        assert isinstance(info, dict)
        assert info["testee_id"] == "baseline_xyz"
        assert info["testee_type"] == "baseline"
        assert "description" in info


class TestHumanJsonTestee:
    """Test HumanJsonTestee implementation."""

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

    def create_submission_file(self, task_id: str) -> Path:
        """Create a temporary submission JSON file."""
        submission_data = {
            "task_id": task_id,
            "testee_id": "human_001",
            "testee_type": "human",
            "approach": {
                "description": "Configure IP addresses and enable interfaces",
                "commands": [
                    {
                        "node": "R1",
                        "commands": [
                            "ip addr add 10.0.0.1/24 dev eth1",
                            "ip link set eth1 up",
                        ],
                    },
                    {
                        "node": "R2",
                        "commands": [
                            "ip addr add 10.0.0.2/24 dev eth1",
                            "ip link set eth1 up",
                        ],
                    },
                ],
            },
        }

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(submission_data, temp_file)
        temp_file.close()

        return Path(temp_file.name)

    def test_create_human_json_testee(self):
        """Test creating a HumanJsonTestee with submission file."""
        task = self.create_simple_task()
        submission_file = self.create_submission_file(task.task_id)

        try:
            testee = HumanJsonTestee(submission_file=str(submission_file))
            assert testee is not None
        finally:
            submission_file.unlink()

    def test_human_json_testee_loads_submission(self):
        """Test that HumanJsonTestee loads submission from file."""
        task = self.create_simple_task()
        submission_file = self.create_submission_file(task.task_id)

        try:
            testee = HumanJsonTestee(submission_file=str(submission_file))
            submission = testee.generate_submission(task)

            assert isinstance(submission, Submission)
            assert submission.task_id == task.task_id
            assert submission.testee_id == "human_001"
            assert submission.testee_type == "human"
        finally:
            submission_file.unlink()

    def test_human_json_testee_loads_commands(self):
        """Test that commands are loaded correctly from JSON."""
        task = self.create_simple_task()
        submission_file = self.create_submission_file(task.task_id)

        try:
            testee = HumanJsonTestee(submission_file=str(submission_file))
            submission = testee.generate_submission(task)

            assert len(submission.approach.commands) == 2
            assert submission.approach.commands[0].node == "R1"
            assert len(submission.approach.commands[0].commands) == 2
            assert "10.0.0.1" in submission.approach.commands[0].commands[0]
        finally:
            submission_file.unlink()

    def test_human_json_testee_invalid_file(self):
        """Test error handling for invalid file path."""
        with pytest.raises(FileNotFoundError):
            testee = HumanJsonTestee(submission_file="/nonexistent/file.json")
            task = self.create_simple_task()
            testee.generate_submission(task)

    def test_human_json_testee_get_testee_info(self):
        """Test getting testee info from HumanJsonTestee."""
        task = self.create_simple_task()
        submission_file = self.create_submission_file(task.task_id)

        try:
            testee = HumanJsonTestee(submission_file=str(submission_file))
            testee.generate_submission(task)  # Load the submission
            info = testee.get_testee_info()

            assert isinstance(info, dict)
            assert info["testee_id"] == "human_001"
            assert info["testee_type"] == "human"
        finally:
            submission_file.unlink()

    def test_human_json_testee_task_id_mismatch(self):
        """Test error when submission task_id doesn't match task."""
        task = self.create_simple_task()
        submission_file = self.create_submission_file("different_task_id")

        try:
            testee = HumanJsonTestee(submission_file=str(submission_file))
            with pytest.raises(ValueError, match="task_id mismatch"):
                testee.generate_submission(task)
        finally:
            submission_file.unlink()

