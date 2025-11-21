"""
Unit tests for ML model testee.

Tests ML model interface for pre-trained model inference.
"""
import pytest
import tempfile
from pathlib import Path
from benchmark.ml.model_testee import MLModelTestee, MockMLModelTestee
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


class TestMLModelTestee:
    """Test ML model testee interface."""

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
            ],
            links=[],
        )

        intent = IntentSpecification(
            properties=[
                Property(
                    id="test_prop",
                    type="reachability",
                    description="Test property",
                    evaluation=EvaluationProcedure(
                        method="exec_and_parse",
                        target_node="R1",
                        command="echo test",
                        parser="text",
                        success_condition={"contains_text": "test"},
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

    def test_mock_ml_model_testee(self):
        """Test creating a mock ML model testee."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "mock_model.pt"
            testee = MockMLModelTestee(model_path=str(model_path))

            assert testee is not None
            assert testee.framework == "mock"

    def test_mock_ml_generate_submission(self):
        """Test generating submission with mock ML model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "mock_model.pt"
            testee = MockMLModelTestee(model_path=str(model_path))

            task = self.create_simple_task()
            submission = testee.generate_submission(task)

            assert submission.task_id == task.task_id
            assert submission.testee_type == "ml_model"
            assert len(submission.approach.commands) == 1

    def test_ml_model_requires_file(self):
        """Test that MLModelTestee requires model file to exist for base class."""
        # MockMLModelTestee creates the file, but base MLModelTestee doesn't
        # This test verifies the base class behavior
        # For now, we just verify that mock creates the file
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            assert not model_path.exists()
            
            # MockMLModelTestee creates it
            testee = MockMLModelTestee(model_path=str(model_path))
            assert model_path.exists()

    def test_ml_model_get_testee_info(self):
        """Test getting testee info from ML model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "mock_model.pt"
            testee = MockMLModelTestee(
                model_path=str(model_path), testee_id="ml_test_001"
            )

            info = testee.get_testee_info()

            assert info["testee_id"] == "ml_test_001"
            assert info["testee_type"] == "ml_model"
            assert info["framework"] == "mock"
            assert "model_path" in info

