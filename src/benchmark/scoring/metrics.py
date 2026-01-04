"""
Scoring metrics calculator.

This module implements the scoring metrics from Section 6.2 of the formalization:
- Score_C: Completeness (fraction of properties satisfied)
- Score_R: Robustness (idempotency)
- Score_X: Syntactic validity (fraction of valid commands)
- Score_E: Efficiency (relative to optimal solution)
- Final: Weighted combination
"""
from typing import List, Optional, Dict

from benchmark.models.results import PropertyEvaluationResult, ScoringResult
from benchmark.models.submission import Approach
from benchmark.models.task import OptimalSolution
from benchmark.executor.command import ExecutionLogEntry


class ScoringCalculator:
    """
    Calculates scoring metrics for benchmark submissions.
    
    Implements the scoring formulas from the formalization document.
    All scores are in the range [0.0, 1.0].
    """
    
    # Default weights for final score calculation
    DEFAULT_WEIGHTS = {
        "completeness": 0.5,
        "robustness": 0.3,
        "syntactic_validity": 0.2,
        "efficiency": 0.0,
    }
    
    def compute_completeness(
        self,
        property_results: List[PropertyEvaluationResult]
    ) -> float:
        """
        Compute completeness score (Score_C).
        
        Formula: |{p ∈ P | p(sf) = true}| / |P|
        
        The fraction of properties that are satisfied.
        
        Args:
            property_results: List of property evaluation results
            
        Returns:
            Completeness score in [0.0, 1.0]
        """
        if not property_results:
            return 0.0
        
        satisfied_count = sum(1 for p in property_results if p.satisfied)
        total_count = len(property_results)
        
        return satisfied_count / total_count
    
    def compute_robustness(
        self,
        property_results: List[PropertyEvaluationResult]
    ) -> float:
        """
        Compute robustness score (Score_R).
        
        Robustness measures idempotency - whether the configuration
        remains valid when re-applied to the final state.
        
        MVP Implementation:
        - Returns 1.0 if all properties are satisfied (completeness = 1.0)
        - Returns 0.0 otherwise
        
        Future Enhancement:
        - Re-execute the approach on the final state
        - Compare property results before and after
        
        Args:
            property_results: List of property evaluation results
            
        Returns:
            Robustness score in [0.0, 1.0]
        """
        # MVP: Simple heuristic based on completeness
        completeness = self.compute_completeness(property_results)
        
        if completeness == 1.0:
            return 1.0
        else:
            return 0.0
    
    def compute_syntactic_validity(
        self,
        execution_log: List[ExecutionLogEntry]
    ) -> float:
        """
        Compute syntactic validity score (Score_X).
        
        The fraction of commands that executed successfully
        (exit code 0, no syntax errors).
        
        Args:
            execution_log: List of command execution log entries
            
        Returns:
            Syntactic validity score in [0.0, 1.0]
        """
        if not execution_log:
            # No commands executed = no data = 0% syntactic validity
            # (prevents inflated scores for agents that fail to run)
            return 0.0
        
        successful_count = sum(1 for entry in execution_log if entry.success)
        total_count = len(execution_log)
        
        return successful_count / total_count
    
    def compute_efficiency(
        self,
        approach: Approach,
        optimal_solution: Optional[OptimalSolution]
    ) -> Optional[float]:
        """
        Compute efficiency score (Score_E).
        
        Formula: min(1, optimal_count / actual_count)
        
        Measures how efficient the solution is compared to the
        optimal (reference) solution.
        
        Args:
            approach: The submitted configuration approach
            optimal_solution: Reference optimal solution (if available)
            
        Returns:
            Efficiency score in [0.0, 1.0], or None if no optimal solution
        """
        if optimal_solution is None:
            return None
        
        # Count total commands in approach
        actual_count = sum(
            len(cmd_seq.commands) 
            for cmd_seq in approach.commands
        )
        
        if actual_count == 0:
            return 0.0
        
        optimal_count = optimal_solution.command_count
        
        # Efficiency is capped at 1.0 (can't be better than optimal)
        efficiency = min(1.0, optimal_count / actual_count)
        
        return efficiency
    
    def compute_final_score(
        self,
        completeness: float,
        robustness: float,
        syntactic_validity: float,
        efficiency: Optional[float],
        weights: Dict[str, float]
    ) -> float:
        """
        Compute final weighted score.
        
        Formula: w_C * C + w_R * R + w_X * X + w_E * E
        
        If efficiency is None, its weight is redistributed proportionally
        to the other metrics.
        
        Args:
            completeness: Completeness score [0.0, 1.0]
            robustness: Robustness score [0.0, 1.0]
            syntactic_validity: Syntactic validity score [0.0, 1.0]
            efficiency: Efficiency score [0.0, 1.0] or None
            weights: Dict of weights for each metric
            
        Returns:
            Final score in [0.0, 1.0]
        """
        # Extract weights
        w_c = weights.get("completeness", self.DEFAULT_WEIGHTS["completeness"])
        w_r = weights.get("robustness", self.DEFAULT_WEIGHTS["robustness"])
        w_x = weights.get("syntactic_validity", self.DEFAULT_WEIGHTS["syntactic_validity"])
        w_e = weights.get("efficiency", self.DEFAULT_WEIGHTS["efficiency"])
        
        if efficiency is None:
            # Redistribute efficiency weight proportionally
            total_without_efficiency = w_c + w_r + w_x
            
            if total_without_efficiency == 0:
                # Edge case: all other weights are 0
                return 0.0
            
            # Normalize weights
            w_c_norm = w_c / total_without_efficiency
            w_r_norm = w_r / total_without_efficiency
            w_x_norm = w_x / total_without_efficiency
            
            final_score = (
                w_c_norm * completeness +
                w_r_norm * robustness +
                w_x_norm * syntactic_validity
            )
        else:
            # Use all weights including efficiency
            final_score = (
                w_c * completeness +
                w_r * robustness +
                w_x * syntactic_validity +
                w_e * efficiency
            )
        
        # Ensure score is in valid range
        return max(0.0, min(1.0, final_score))
    
    def compute_all_scores(
        self,
        property_results: List[PropertyEvaluationResult],
        execution_log: List[ExecutionLogEntry],
        approach: Approach,
        optimal_solution: Optional[OptimalSolution] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> ScoringResult:
        """
        Compute all scoring metrics and return a complete ScoringResult.
        
        Args:
            property_results: List of property evaluation results
            execution_log: List of command execution log entries
            approach: The submitted configuration approach
            optimal_solution: Reference optimal solution (optional)
            weights: Custom weights for final score (optional, uses defaults if None)
            
        Returns:
            Complete ScoringResult with all metrics
        """
        # Use default weights if not provided
        if weights is None:
            weights = self.DEFAULT_WEIGHTS.copy()
        
        # Compute individual metrics
        completeness = self.compute_completeness(property_results)
        robustness = self.compute_robustness(property_results)
        syntactic_validity = self.compute_syntactic_validity(execution_log)
        efficiency = self.compute_efficiency(approach, optimal_solution)
        
        # Compute final weighted score
        final_score = self.compute_final_score(
            completeness,
            robustness,
            syntactic_validity,
            efficiency,
            weights
        )
        
        # Build and return result
        return ScoringResult(
            completeness=completeness,
            robustness=robustness,
            syntactic_validity=syntactic_validity,
            efficiency=efficiency,
            final_score=final_score,
            weights=weights
        )

