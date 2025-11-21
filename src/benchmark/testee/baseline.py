"""
Baseline testee implementation.

Generates baseline (empty/minimal) submissions for comparison purposes.
"""
from typing import Dict, Any, List
from benchmark.testee.base import BaseTestee
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission, Approach, CommandSequence


class BaselineTestee(BaseTestee):
    """
    Baseline testee that generates empty/minimal submissions.
    
    Used as a control/baseline for comparison with other testees.
    Generates submissions with empty command sequences for all nodes.
    """

    def __init__(self, testee_id: str = "baseline"):
        """
        Initialize the baseline testee.
        
        Args:
            testee_id: Unique identifier for this baseline testee
        """
        self.testee_id = testee_id
        self.testee_type = "baseline"

    def generate_submission(self, task: TaskDefinition) -> Submission:
        """
        Generate a baseline submission with minimal commands.
        
        Creates a submission with command sequences for all nodes in the
        topology, but with minimal (no-op) commands.
        
        Args:
            task: TaskDefinition to generate submission for
        
        Returns:
            Submission with minimal commands for all nodes
        """
        # Create minimal command sequences for all nodes
        # Use a no-op command since CommandSequence requires at least one command
        commands: List[CommandSequence] = []
        for node in task.topology.nodes:
            commands.append(CommandSequence(node=node.name, commands=["# baseline"]))

        approach = Approach(
            description="Baseline (empty) configuration",
            commands=commands,
        )

        return Submission(
            task_id=task.task_id,
            testee_id=self.testee_id,
            testee_type=self.testee_type,
            approach=approach,
        )

    def get_testee_info(self) -> Dict[str, Any]:
        """
        Return metadata about this baseline testee.
        
        Returns:
            Dictionary with testee information
        """
        return {
            "testee_id": self.testee_id,
            "testee_type": self.testee_type,
            "description": "Baseline testee with empty commands (control)",
            "version": "1.0",
        }

