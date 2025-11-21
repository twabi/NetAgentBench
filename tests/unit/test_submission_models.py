"""
Unit tests for Submission Pydantic models.
Following TDD: Write tests first for submission-related models.
"""
import pytest
from pydantic import ValidationError


class TestCommandSequence:
    """Test CommandSequence model"""

    def test_command_sequence_creation(self):
        """Test creating a command sequence"""
        from benchmark.models.submission import CommandSequence

        cmd_seq = CommandSequence(
            node="R1",
            commands=[
                "vtysh -c 'conf t' -c 'router bgp 65001'",
                "vtysh -c 'conf t' -c 'neighbor 192.168.1.2 remote-as 65002'",
            ],
        )

        assert cmd_seq.node == "R1"
        assert len(cmd_seq.commands) == 2
        assert "bgp" in cmd_seq.commands[0]

    def test_command_sequence_requires_node(self):
        """Test that command sequence requires a node"""
        from benchmark.models.submission import CommandSequence

        with pytest.raises(ValidationError) as exc_info:
            CommandSequence(commands=["test"])

        assert "node" in str(exc_info.value)

    def test_command_sequence_requires_commands(self):
        """Test that command sequence requires commands"""
        from benchmark.models.submission import CommandSequence

        with pytest.raises(ValidationError) as exc_info:
            CommandSequence(node="R1")

        assert "commands" in str(exc_info.value)

    def test_command_sequence_requires_at_least_one_command(self):
        """Test that command sequence requires at least one command"""
        from benchmark.models.submission import CommandSequence

        with pytest.raises(ValidationError) as exc_info:
            CommandSequence(node="R1", commands=[])

        assert "at least 1 item" in str(exc_info.value).lower()

    def test_command_sequence_json_serialization(self):
        """Test JSON serialization"""
        from benchmark.models.submission import CommandSequence

        cmd_seq = CommandSequence(node="R1", commands=["echo test"])
        json_str = cmd_seq.model_dump_json()

        assert "R1" in json_str
        assert "echo test" in json_str


class TestApproach:
    """Test Approach model"""

    def test_approach_creation_with_description(self):
        """Test creating an approach with description"""
        from benchmark.models.submission import Approach, CommandSequence

        commands = [
            CommandSequence(node="R1", commands=["config1"]),
            CommandSequence(node="R2", commands=["config2"]),
        ]

        approach = Approach(
            description="Configure BGP peering",
            commands=commands,
        )

        assert approach.description == "Configure BGP peering"
        assert len(approach.commands) == 2
        assert approach.commands[0].node == "R1"

    def test_approach_requires_commands(self):
        """Test that approach requires at least one command"""
        from benchmark.models.submission import Approach

        with pytest.raises(ValidationError) as exc_info:
            Approach(description="Test", commands=[])

        assert "at least 1 item" in str(exc_info.value).lower()

    def test_approach_description_optional(self):
        """Test that description is optional"""
        from benchmark.models.submission import Approach, CommandSequence

        commands = [CommandSequence(node="R1", commands=["test"])]
        approach = Approach(commands=commands)

        assert approach.description is None
        assert len(approach.commands) == 1

    def test_approach_with_multiple_nodes(self):
        """Test approach with commands for multiple nodes"""
        from benchmark.models.submission import Approach, CommandSequence

        commands = [
            CommandSequence(node="R1", commands=["cmd1", "cmd2"]),
            CommandSequence(node="R2", commands=["cmd3"]),
            CommandSequence(node="R3", commands=["cmd4", "cmd5", "cmd6"]),
        ]

        approach = Approach(description="Multi-node config", commands=commands)

        assert len(approach.commands) == 3
        # Verify we can access specific nodes
        assert approach.commands[0].node == "R1"
        assert len(approach.commands[0].commands) == 2
        assert approach.commands[2].node == "R3"
        assert len(approach.commands[2].commands) == 3

    def test_approach_json_round_trip(self):
        """Test JSON serialization and deserialization"""
        from benchmark.models.submission import Approach, CommandSequence
        import json

        commands = [
            CommandSequence(node="R1", commands=["test1", "test2"]),
        ]
        approach = Approach(description="Test approach", commands=commands)

        # Serialize
        json_str = approach.model_dump_json()
        json_dict = json.loads(json_str)

        # Deserialize
        approach_restored = Approach(**json_dict)

        assert approach_restored.description == approach.description
        assert len(approach_restored.commands) == len(approach.commands)
        assert approach_restored.commands[0].node == approach.commands[0].node


class TestSubmission:
    """Test Submission model"""

    def test_submission_creation_complete(self):
        """Test creating a complete submission"""
        from benchmark.models.submission import Submission, Approach, CommandSequence

        commands = [CommandSequence(node="R1", commands=["test"])]
        approach = Approach(description="Test", commands=commands)

        submission = Submission(
            task_id="task_001",
            testee_id="gpt4_20251013",
            testee_type="llm",
            approach=approach,
        )

        assert submission.task_id == "task_001"
        assert submission.testee_id == "gpt4_20251013"
        assert submission.testee_type == "llm"
        assert submission.approach.description == "Test"

    def test_submission_requires_task_id(self):
        """Test that submission requires task_id"""
        from benchmark.models.submission import Submission, Approach, CommandSequence

        commands = [CommandSequence(node="R1", commands=["test"])]
        approach = Approach(commands=commands)

        with pytest.raises(ValidationError) as exc_info:
            Submission(
                testee_id="test",
                testee_type="llm",
                approach=approach,
            )

        assert "task_id" in str(exc_info.value)

    def test_submission_requires_testee_id(self):
        """Test that submission requires testee_id"""
        from benchmark.models.submission import Submission, Approach, CommandSequence

        commands = [CommandSequence(node="R1", commands=["test"])]
        approach = Approach(commands=commands)

        with pytest.raises(ValidationError) as exc_info:
            Submission(
                task_id="task_001",
                testee_type="llm",
                approach=approach,
            )

        assert "testee_id" in str(exc_info.value)

    def test_submission_requires_testee_type(self):
        """Test that submission requires testee_type"""
        from benchmark.models.submission import Submission, Approach, CommandSequence

        commands = [CommandSequence(node="R1", commands=["test"])]
        approach = Approach(commands=commands)

        with pytest.raises(ValidationError) as exc_info:
            Submission(
                task_id="task_001",
                testee_id="test",
                approach=approach,
            )

        assert "testee_type" in str(exc_info.value)

    def test_submission_requires_approach(self):
        """Test that submission requires an approach"""
        from benchmark.models.submission import Submission

        with pytest.raises(ValidationError) as exc_info:
            Submission(
                task_id="task_001",
                testee_id="test",
                testee_type="llm",
            )

        assert "approach" in str(exc_info.value)

    def test_submission_testee_types(self):
        """Test different testee types"""
        from benchmark.models.submission import Submission, Approach, CommandSequence

        commands = [CommandSequence(node="R1", commands=["test"])]
        approach = Approach(commands=commands)

        # Test with LLM
        sub_llm = Submission(
            task_id="task_001",
            testee_id="gpt4",
            testee_type="llm",
            approach=approach,
        )
        assert sub_llm.testee_type == "llm"

        # Test with human
        sub_human = Submission(
            task_id="task_001",
            testee_id="expert_1",
            testee_type="human",
            approach=approach,
        )
        assert sub_human.testee_type == "human"

        # Test with baseline
        sub_baseline = Submission(
            task_id="task_001",
            testee_id="baseline_v1",
            testee_type="baseline",
            approach=approach,
        )
        assert sub_baseline.testee_type == "baseline"

    def test_submission_json_round_trip(self):
        """Test complete JSON serialization and deserialization"""
        from benchmark.models.submission import Submission, Approach, CommandSequence
        import json

        # Create a complete submission
        commands = [
            CommandSequence(node="R1", commands=["cmd1", "cmd2"]),
            CommandSequence(node="R2", commands=["cmd3"]),
        ]
        approach = Approach(description="Configure network", commands=commands)
        submission = Submission(
            task_id="bgp_basic_001",
            testee_id="claude_20251013",
            testee_type="llm",
            approach=approach,
        )

        # Serialize to JSON
        json_str = submission.model_dump_json()

        # Deserialize from JSON
        json_dict = json.loads(json_str)
        submission_restored = Submission(**json_dict)

        # Verify all fields match
        assert submission_restored.task_id == submission.task_id
        assert submission_restored.testee_id == submission.testee_id
        assert submission_restored.testee_type == submission.testee_type
        assert len(submission_restored.approach.commands) == len(submission.approach.commands)
        assert submission_restored.approach.commands[0].node == "R1"
        assert submission_restored.approach.commands[1].node == "R2"

    def test_submission_matches_task_id_format(self):
        """Test that submission can reference any task_id format"""
        from benchmark.models.submission import Submission, Approach, CommandSequence

        commands = [CommandSequence(node="R1", commands=["test"])]
        approach = Approach(commands=commands)

        # Test various task_id formats
        task_ids = [
            "simple_001",
            "bgp_basic_001",
            "ospf_3node_002",
            "task-with-dashes",
            "TASK_UPPERCASE",
        ]

        for task_id in task_ids:
            submission = Submission(
                task_id=task_id,
                testee_id="test",
                testee_type="llm",
                approach=approach,
            )
            assert submission.task_id == task_id


class TestIntegrationWithTaskModels:
    """Test that submission models integrate well with task models"""

    def test_submission_for_complete_workflow(self):
        """Test creating a submission that matches a task"""
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
        from benchmark.models.submission import Submission, Approach, CommandSequence

        # Create a task
        nodes = [
            Node(name="R1", type=NodeType.ROUTER),
            Node(name="R2", type=NodeType.ROUTER),
        ]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])

        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="test",
            parser="text",
            success_condition={},
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

        task = TaskDefinition(
            task_id="integration_test_001",
            description="Integration test",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        # Create a submission for this task
        commands = [
            CommandSequence(node="R1", commands=["config for R1"]),
            CommandSequence(node="R2", commands=["config for R2"]),
        ]
        approach = Approach(description="Solution", commands=commands)
        submission = Submission(
            task_id=task.task_id,  # References the task
            testee_id="test_integration",
            testee_type="llm",
            approach=approach,
        )

        # Verify they match
        assert submission.task_id == task.task_id

        # Verify submission targets nodes that exist in task
        submission_nodes = {cmd.node for cmd in submission.approach.commands}
        task_nodes = {node.name for node in task.topology.nodes}
        assert submission_nodes.issubset(task_nodes)

