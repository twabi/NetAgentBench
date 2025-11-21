"""
Validity checker for solutions.

This module implements Theorem 1 (Valid Solution) from the formalization:
A solution is valid if and only if:
(a) Syntactic Correctness: All commands are valid for the platform
(b) Semantic Completeness: All properties are satisfied
"""
from typing import List

from benchmark.models.results import PropertyEvaluationResult, ValidityCheck
from benchmark.executor.command import ExecutionLogEntry


class ValidityChecker:
    """
    Checks solution validity per Theorem 1.
    
    A solution is considered valid when:
    - Condition A (Syntactic): All commands execute successfully
    - Condition B (Semantic): All properties are satisfied
    - Valid Solution: A AND B
    """
    
    def check_validity(
        self,
        property_results: List[PropertyEvaluationResult],
        execution_log: List[ExecutionLogEntry]
    ) -> ValidityCheck:
        """
        Check if a solution is valid according to Theorem 1.
        
        Args:
            property_results: List of property evaluation results
            execution_log: List of command execution log entries
            
        Returns:
            ValidityCheck with condition results and overall validity
        """
        # Condition A: Syntactic Correctness
        # All commands must execute successfully (exit code 0)
        condition_a_syntactic = self._check_syntactic_correctness(execution_log)
        
        # Condition B: Semantic Completeness
        # All properties must be satisfied
        condition_b_semantic = self._check_semantic_completeness(property_results)
        
        # Valid solution: Both conditions must be true
        is_valid_solution = condition_a_syntactic and condition_b_semantic
        
        return ValidityCheck(
            is_valid_solution=is_valid_solution,
            condition_a_syntactic=condition_a_syntactic,
            condition_b_semantic=condition_b_semantic
        )
    
    def _check_syntactic_correctness(
        self,
        execution_log: List[ExecutionLogEntry]
    ) -> bool:
        """
        Check syntactic correctness (Condition A).
        
        All commands must have executed successfully.
        
        Args:
            execution_log: List of command execution log entries
            
        Returns:
            True if all commands succeeded, False otherwise
        """
        if not execution_log:
            # Convention: No commands means syntactic correctness holds
            # (vacuously true - no commands to fail)
            return True
        
        # Check if all commands succeeded
        return all(entry.success for entry in execution_log)
    
    def _check_semantic_completeness(
        self,
        property_results: List[PropertyEvaluationResult]
    ) -> bool:
        """
        Check semantic completeness (Condition B).
        
        All properties must be satisfied.
        
        Args:
            property_results: List of property evaluation results
            
        Returns:
            True if all properties satisfied, False otherwise
        """
        if not property_results:
            # Convention: No properties means semantic completeness holds
            # (vacuously true - no properties to fail)
            return True
        
        # Check if all properties are satisfied
        return all(prop.satisfied for prop in property_results)

