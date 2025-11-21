"""
Base testee interface for the benchmark system.

Defines the abstract interface that all testee types must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission


class BaseTestee(ABC):
    """
    Abstract base class for all testee types.
    
    A testee is any entity (human, LLM, ML model, baseline) that can
    generate network configuration submissions for benchmark tasks.
    
    All testees must implement:
    - generate_submission: Create a submission for a given task
    - get_testee_info: Return metadata about the testee
    """

    @abstractmethod
    def generate_submission(self, task: TaskDefinition) -> Submission:
        """
        Generate a configuration submission for the given task.
        
        Args:
            task: TaskDefinition specifying the network configuration problem
        
        Returns:
            Submission containing the testee's configuration approach
        
        Raises:
            Exception: If submission generation fails
        """
        pass

    @abstractmethod
    def get_testee_info(self) -> Dict[str, Any]:
        """
        Return metadata about this testee.
        
        Returns:
            Dictionary with testee information including:
            - testee_id: Unique identifier
            - testee_type: Type (human, llm, ml_model, baseline)
            - description: Human-readable description
            - Additional type-specific metadata
        """
        pass

