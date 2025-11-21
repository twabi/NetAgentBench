"""
Observation executor for collecting command outputs from network nodes.

This module handles the execution of evaluation procedures to observe
the state of the network.
"""
import time
from dataclasses import dataclass
from typing import Optional

from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.models.task import EvaluationProcedure
from benchmark.executor.command import CommandExecutor


@dataclass
class ObservationResult:
    """
    Result of an observation execution.
    
    Contains the raw output from the observation command along with
    metadata about the execution.
    """
    raw_output: str
    stderr: str
    execution_time: float
    success: bool
    exit_code: int
    error: Optional[str] = None


class ObservationExecutor:
    """
    Executes observation commands to collect network state.
    
    Used by the property evaluator to gather information from
    network nodes for evaluation.
    """

    def __init__(self):
        """Initialize the observation executor."""
        self.command_executor = CommandExecutor()

    def observe(
        self,
        infrastructure: InfrastructureProvider,
        topology_id: str,
        evaluation_proc: EvaluationProcedure
    ) -> ObservationResult:
        """
        Execute an observation command and collect output.
        
        Args:
            infrastructure: Infrastructure provider for container name resolution
            topology_id: ID of the provisioned topology
            evaluation_proc: Evaluation procedure specifying what to observe
            
        Returns:
            ObservationResult containing the command output and metadata
        """
        start_time = time.time()
        
        try:
            # Get container name for the target node
            container_name = infrastructure.get_node_container_name(
                topology_id,
                evaluation_proc.target_node
            )
            
            # Execute the observation command
            stdout, stderr, exit_code = self.command_executor.exec_on_node(
                container_name,
                evaluation_proc.command
            )
            
            execution_time = time.time() - start_time
            
            # Success if exit code is 0
            success = (exit_code == 0)
            
            return ObservationResult(
                raw_output=stdout,
                stderr=stderr,
                execution_time=execution_time,
                success=success,
                exit_code=exit_code,
                error=None if success else f"Command exited with code {exit_code}"
            )
            
        except Exception as e:
            # Handle any errors gracefully
            execution_time = time.time() - start_time
            
            return ObservationResult(
                raw_output="",
                stderr="",
                execution_time=execution_time,
                success=False,
                exit_code=-1,
                error=f"Exception during observation: {str(e)}"
            )

