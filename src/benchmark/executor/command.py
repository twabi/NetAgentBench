"""
Command executor for running commands on network nodes.

This module handles execution of configuration commands on containers
and logging of execution results.
"""
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import docker
from docker.errors import DockerException, NotFound

from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.models.submission import Approach


@dataclass
class ExecutionLogEntry:
    """
    Log entry for a single command execution.
    
    Captures all relevant information about command execution
    for debugging, analysis, and research purposes.
    """
    timestamp: datetime
    node: str
    command: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    error: Optional[str] = None


class CommandExecutor:
    """
    Executes commands on network nodes (containers).
    
    Uses Docker SDK to execute commands on running containers.
    Handles errors gracefully and provides detailed execution logs.
    """

    def __init__(self):
        """Initialize the command executor."""
        self._docker_client = None

    @property
    def docker_client(self):
        """Lazy initialization of Docker client."""
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def exec_on_node(
        self, 
        container_name: str, 
        command: str, 
        timeout: int = 30
    ) -> Tuple[str, str, int]:
        """
        Execute a command on a container node.
        
        Args:
            container_name: Name of the container to execute on
            command: Command string to execute
            timeout: Timeout in seconds (default: 30)
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
            - stdout: Standard output as string
            - stderr: Standard error as string
            - exit_code: Exit code (0 for success)
            
        Raises:
            NotFound: If container doesn't exist
            DockerException: If Docker operation fails
        """
        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)
            
            # Execute command
            # Note: Docker exec_run returns (exit_code, output)
            # By default, stderr is merged into stdout
            exit_code, output = container.exec_run(
                command,
                stdout=True,
                stderr=True,
                demux=False,  # Don't separate stdout/stderr
                timeout=timeout,
            )
            
            # Decode output
            if isinstance(output, bytes):
                stdout = output.decode('utf-8', errors='replace')
            else:
                stdout = str(output) if output else ""
            
            # For this implementation, stderr is merged into stdout
            # In future versions, we could use demux=True to separate them
            stderr = ""
            
            return stdout, stderr, exit_code
            
        except NotFound:
            raise NotFound(f"Container '{container_name}' not found")
        except DockerException as e:
            raise DockerException(f"Docker error executing command: {e}")

    def apply_approach(
        self,
        infrastructure: InfrastructureProvider,
        topology_id: str,
        approach: Approach,
        convergence_timeout: int
    ) -> List[ExecutionLogEntry]:
        """
        Apply a complete configuration approach to the network.
        
        Executes all commands in the approach sequentially, continuing
        even if individual commands fail. This allows partial configurations
        to be evaluated and scored.
        
        Args:
            infrastructure: Infrastructure provider for container name resolution
            topology_id: ID of the provisioned topology
            approach: Configuration approach to apply
            convergence_timeout: Seconds to wait after all commands for convergence
            
        Returns:
            List of ExecutionLogEntry objects, one per command executed
        """
        log_entries: List[ExecutionLogEntry] = []
        
        # Iterate through all command sequences
        for cmd_sequence in approach.commands:
            node_name = cmd_sequence.node
            
            # Get container name for this node
            try:
                container_name = infrastructure.get_node_container_name(
                    topology_id, 
                    node_name
                )
            except Exception as e:
                # If we can't get container name, log error for all commands
                for command in cmd_sequence.commands:
                    log_entries.append(ExecutionLogEntry(
                        timestamp=datetime.now(),
                        node=node_name,
                        command=command,
                        success=False,
                        stdout="",
                        stderr="",
                        exit_code=-1,
                        execution_time=0.0,
                        error=f"Failed to get container name: {str(e)}"
                    ))
                continue
            
            # Execute each command in sequence
            for command in cmd_sequence.commands:
                start_time = time.time()
                
                try:
                    # Execute the command
                    stdout, stderr, exit_code = self.exec_on_node(
                        container_name, 
                        command
                    )
                    
                    execution_time = time.time() - start_time
                    
                    # Determine success (exit code 0 means success)
                    success = (exit_code == 0)
                    
                    # Create log entry
                    log_entries.append(ExecutionLogEntry(
                        timestamp=datetime.now(),
                        node=node_name,
                        command=command,
                        success=success,
                        stdout=stdout,
                        stderr=stderr,
                        exit_code=exit_code,
                        execution_time=execution_time,
                        error=None if success else "Command exited with non-zero code"
                    ))
                    
                except Exception as e:
                    # Command execution failed with exception
                    execution_time = time.time() - start_time
                    
                    log_entries.append(ExecutionLogEntry(
                        timestamp=datetime.now(),
                        node=node_name,
                        command=command,
                        success=False,
                        stdout="",
                        stderr="",
                        exit_code=-1,
                        execution_time=execution_time,
                        error=f"Exception during execution: {str(e)}"
                    ))
                
                # Continue to next command (don't abort on failure)
        
        # Wait for convergence after all commands
        if convergence_timeout > 0:
            time.sleep(convergence_timeout)
        
        return log_entries

