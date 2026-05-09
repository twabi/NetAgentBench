"""
Benchmark-specific task definition.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class BenchmarkTask:
    """
    Task definition for network benchmark.
    
    Extends the generic AgentTask with network-specific fields.
    """
    task_id: str
    description: str
    nodes: List[str]
    properties: List[Dict[str, Any]]
    turn_limit: int = 50
    time_limit: float = 600.0
    
    def to_agent_context(self) -> Dict[str, Any]:
        """Convert to agent context dict for generic agent."""
        return {
            "nodes": self.nodes,
            "properties": self.properties,
        }
