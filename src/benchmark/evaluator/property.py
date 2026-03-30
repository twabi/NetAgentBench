"""
Property evaluator for evaluating network properties.

This module orchestrates observation collection, parsing, and
property satisfaction evaluation.
"""
import time
from typing import List

from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.models.task import Property
from benchmark.models.results import PropertyEvaluationResult
from benchmark.executor.observation import ObservationExecutor
from benchmark.evaluator.parsers import ParserRegistry


class PropertyEvaluator:
    """
    Evaluates network properties by executing observations and parsing results.
    
    Orchestrates the complete property evaluation workflow:
    1. Execute observation command on target node
    2. Parse output using appropriate parser
    3. Evaluate success condition
    4. Return detailed evaluation result
    """
    
    def __init__(self):
        """Initialize the property evaluator."""
        self.observation_executor = ObservationExecutor()
        self.parser_registry = ParserRegistry()
    
    def evaluate_property(
        self,
        infrastructure: InfrastructureProvider,
        topology_id: str,
        property_spec: Property
    ) -> PropertyEvaluationResult:
        """
        Evaluate a single property.
        
        Args:
            infrastructure: Infrastructure provider for node access
            topology_id: ID of the provisioned topology
            property_spec: Property specification to evaluate
            
        Returns:
            PropertyEvaluationResult with evaluation outcome and details
        """
        start_time = time.time()
        
        try:
            # Step 1: Execute observation
            observation_result = self.observation_executor.observe(
                infrastructure,
                topology_id,
                property_spec.evaluation
            )
            
            # Check if observation itself failed
            if not observation_result.success:
                cond = (
                    property_spec.evaluation.success_condition
                    if property_spec.evaluation else {}
                ) or {}
                has_text_cond = any(
                    k in cond
                    for k in (
                        "contains_text",
                        "not_contains_text",
                        "contains_all",
                        "not_contains_all",
                    )
                )
                if not has_text_cond or observation_result.exit_code == -1:
                    execution_time = time.time() - start_time
                    return PropertyEvaluationResult(
                        property_id=property_spec.id,
                        satisfied=False,
                        observation_raw=observation_result.raw_output,
                        observation_parsed=None,
                        evaluation_time_seconds=execution_time,
                        error_message=observation_result.error or "Observation command failed"
                    )
                # else: command ran but returned non-zero — try text-based evaluation
            
            # Step 2: Get parser for this evaluation
            try:
                parser = self.parser_registry.get_parser(
                    property_spec.evaluation.parser
                )
            except ValueError as e:
                execution_time = time.time() - start_time
                return PropertyEvaluationResult(
                    property_id=property_spec.id,
                    satisfied=False,
                    observation_raw=observation_result.raw_output,
                    observation_parsed=None,
                    evaluation_time_seconds=execution_time,
                    error_message=f"Invalid parser: {str(e)}"
                )
            
            # Step 3: Parse output and evaluate condition
            try:
                satisfied, parsed_data = parser.parse(
                    observation_result.raw_output,
                    property_spec.evaluation.success_condition
                )
            except Exception as e:
                execution_time = time.time() - start_time
                return PropertyEvaluationResult(
                    property_id=property_spec.id,
                    satisfied=False,
                    observation_raw=observation_result.raw_output,
                    observation_parsed=None,
                    evaluation_time_seconds=execution_time,
                    error_message=f"Parsing failed: {str(e)}"
                )
            
            # Step 4: Build result
            execution_time = time.time() - start_time
            
            return PropertyEvaluationResult(
                property_id=property_spec.id,
                satisfied=satisfied,
                observation_raw=observation_result.raw_output,
                observation_parsed=parsed_data,
                evaluation_time_seconds=execution_time,
                error_message=None
            )
            
        except Exception as e:
            # Catch-all for any unexpected errors
            execution_time = time.time() - start_time
            return PropertyEvaluationResult(
                property_id=property_spec.id,
                satisfied=False,
                observation_raw="",
                observation_parsed=None,
                evaluation_time_seconds=execution_time,
                error_message=f"Unexpected error during evaluation: {str(e)}"
            )
    
    def evaluate_all_properties(
        self,
        infrastructure: InfrastructureProvider,
        topology_id: str,
        properties: List[Property]
    ) -> List[PropertyEvaluationResult]:
        """
        Evaluate all properties in a list.
        
        Continues evaluation even if individual properties fail,
        ensuring all properties are evaluated.
        
        Args:
            infrastructure: Infrastructure provider for node access
            topology_id: ID of the provisioned topology
            properties: List of properties to evaluate
            
        Returns:
            List of PropertyEvaluationResult objects, one per property
        """
        results = []
        
        for property_spec in properties:
            # Evaluate each property independently
            result = self.evaluate_property(
                infrastructure,
                topology_id,
                property_spec
            )
            results.append(result)
            
            # Continue to next property regardless of success/failure
        
        return results

