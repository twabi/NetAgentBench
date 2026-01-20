"""
Pydantic models for benchmark results.

This module defines all models related to benchmark execution results,
including property evaluation results, scoring metrics, and complete
benchmark run results.

Based on the FSM formalization document.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# Property Evaluation Results
# ============================================================================


class PropertyEvaluationResult(BaseModel):
    """
    Result of evaluating a single network property.
    
    Captures whether the property was satisfied, the observation data,
    and any errors that occurred during evaluation.
    """

    property_id: str = Field(..., description="Property identifier")
    satisfied: bool = Field(..., description="Whether the property was satisfied")
    observation_raw: str = Field(..., description="Raw output from observation")
    observation_parsed: Optional[Dict[str, Any]] = Field(
        None, description="Parsed observation data"
    )
    evaluation_time_seconds: float = Field(
        ..., description="Time taken to evaluate this property"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if evaluation failed"
    )


# ============================================================================
# Scoring Metrics (Section 6.2 in formalization)
# ============================================================================


class ScoringResult(BaseModel):
    """
    Complete scoring metrics for a benchmark run.
    
    Implements the scoring metrics from Section 6.2 of the formalization:
    - Score_C: Completeness (fraction of properties satisfied)
    - Score_R: Robustness (idempotency)
    - Score_X: Syntactic validity (fraction of valid commands)
    - Score_E: Efficiency (relative to optimal solution)
    - Final: Weighted combination
    """

    completeness: float = Field(
        ..., ge=0.0, le=1.0, description="Score_C: Fraction of properties satisfied"
    )
    robustness: float = Field(
        ..., ge=0.0, le=1.0, description="Score_R: Idempotency score"
    )
    syntactic_validity: float = Field(
        ..., ge=0.0, le=1.0, description="Score_X: Fraction of valid commands"
    )
    efficiency: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Score_E: Efficiency vs optimal"
    )
    final_score: float = Field(
        ..., ge=0.0, le=1.0, description="Weighted final score"
    )
    weights: Dict[str, float] = Field(
        default_factory=dict, description="Weights used in scoring"
    )


# ============================================================================
# Execution Metrics
# ============================================================================


class ExecutionMetrics(BaseModel):
    """
    Timing metrics for benchmark execution.
    
    Captures the time taken for each phase of the benchmark,
    useful for research and performance analysis.
    
    Multi-turn fields are optional and only populated for multi-turn runs.
    """

    infrastructure_provision_time: float = Field(
        ..., description="Time to provision infrastructure (seconds)"
    )
    config_execution_time: float = Field(
        ..., description="Time to execute configuration (seconds)"
    )
    convergence_time: float = Field(
        ..., description="Time spent waiting for convergence (seconds)"
    )
    evaluation_time: float = Field(
        ..., description="Time to evaluate all properties (seconds)"
    )
    total_time: float = Field(..., description="Total benchmark execution time (seconds)")
    
    # Multi-turn specific fields
    is_multi_turn: bool = Field(
        False, description="Whether this was a multi-turn session"
    )
    turns_to_complete: Optional[int] = Field(
        None, description="Number of config commands used (multi-turn only)"
    )
    time_to_complete: Optional[float] = Field(
        None, description="Actual session duration in seconds (multi-turn only)"
    )
    termination_reason: Optional[str] = Field(
        None, description="How session ended: 'submitted', 'timeout', 'turn_limit' (multi-turn only)"
    )
    tool_usage: Optional[Dict[str, int]] = Field(
        None, description="Tool usage counts e.g. {'exec_command': 5, 'get_nodes': 1} (multi-turn only)"
    )
    total_commands: Optional[int] = Field(
        None, description="Total number of commands executed by agent (multi-turn only)"
    )
    failed_commands: Optional[int] = Field(
        None, description="Number of commands that returned non-zero exit code (multi-turn only)"
    )
    token_usage: Optional[Dict[str, int]] = Field(
        None, description="Token usage: prompt_tokens, completion_tokens, total_tokens (multi-turn only)"
    )
    agent_conversations: Optional[List[Dict[str, Any]]] = Field(
        None, description="Inter-agent message log for multi-agent patterns (multi-turn only)"
    )


# ============================================================================
# Validity Check (Theorem 1 in formalization)
# ============================================================================


class ValidityCheck(BaseModel):
    """
    Validity check per Theorem 1 (Valid Solution) in the formalization.
    
    A solution is valid if and only if:
    (a) Syntactic Correctness: All commands are valid for platform
    (b) Semantic Completeness: All properties are satisfied
    
    is_valid_solution = condition_a AND condition_b
    """

    is_valid_solution: bool = Field(
        ..., description="Whether the solution is valid (per Theorem 1)"
    )
    condition_a_syntactic: bool = Field(
        ..., description="Condition (a): All commands syntactically valid"
    )
    condition_b_semantic: bool = Field(
        ..., description="Condition (b): All properties satisfied"
    )


# ============================================================================
# Main Benchmark Result Model
# ============================================================================


class BenchmarkResult(BaseModel):
    """
    Complete benchmark execution result.
    
    This is the main output model that captures everything about a benchmark run:
    - What task was run
    - Who submitted the solution
    - Whether properties were satisfied
    - Scoring metrics
    - Validity determination
    - Execution timing
    - Complete execution log
    
    Designed for:
    - Storage and later analysis
    - Research data collection
    - Comparative studies (LLM vs human, etc.)
    """

    run_id: str = Field(..., description="Unique identifier for this benchmark run")
    timestamp: datetime = Field(..., description="When the benchmark was executed")
    task_id: str = Field(..., description="Task that was evaluated")
    testee_id: str = Field(..., description="Testee who submitted the solution")
    testee_type: str = Field(..., description="Type of testee (llm, human, baseline)")
    evaluation_mode: str = Field(
        "single_turn", description="Evaluation mode: 'single_turn' or 'multi_turn'"
    )
    model_version: Optional[str] = Field(
        None, description="Model version or identifier (e.g., 'gpt-4-0125-preview')"
    )
    success: bool = Field(
        ..., description="Whether the benchmark completed without errors"
    )
    property_results: List[PropertyEvaluationResult] = Field(
        ..., description="Results for each property evaluation"
    )
    scoring: ScoringResult = Field(..., description="Scoring metrics")
    validity: ValidityCheck = Field(..., description="Validity check (Theorem 1)")
    metrics: ExecutionMetrics = Field(..., description="Execution timing metrics")
    execution_log: List[str] = Field(
        default_factory=list, description="Complete execution log"
    )
    errors: List[str] = Field(
        default_factory=list, description="Errors encountered during execution"
    )
    final_state: Optional[Dict[str, Any]] = Field(
        None, description="Final network state (if captured)"
    )
    reasoning_trace: List[Dict[str, Any]] = Field(
        default_factory=list, description="Agent reasoning trace (multi-turn only)"
    )


# ============================================================================
# Aggregate Result Models (Phase 10)
# ============================================================================


class PropertyExecutionResult(BaseModel):
    """
    Aggregated results for all tasks of a specific property type.
    
    When running multiple tasks for a property type (e.g., all reachability tasks),
    this model aggregates the individual BenchmarkResult objects and provides
    summary statistics.
    """

    property_type: str = Field(..., description="Property type identifier")
    total_tasks: int = Field(..., ge=0, description="Total number of tasks executed")
    successful_tasks: int = Field(
        ..., ge=0, description="Number of tasks with valid solutions"
    )
    results: List[BenchmarkResult] = Field(
        default_factory=list, description="Individual benchmark results"
    )
    average_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average final_score across all tasks"
    )
    aggregate_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Aggregated metrics (avg completeness, robustness, etc.)",
    )


class BenchmarkRunResult(BaseModel):
    """
    Complete results for a multi-task benchmark run across property types.
    
    This is the top-level result model when running a benchmark with multiple
    tasks across one or more property types. It aggregates PropertyExecutionResult
    objects and provides overall statistics.
    
    The overall_average_score is the mean of all individual task final_scores
    across all property types (not the mean of property averages).
    """

    run_id: str = Field(..., description="Unique identifier for this benchmark run")
    testee_id: str = Field(..., description="Testee identifier")
    testee_type: str = Field(
        ..., description="Type of testee (llm, human, ml_model, baseline)"
    )
    evaluation_mode: str = Field(
        "single_turn", description="Evaluation mode: 'single_turn' or 'multi_turn'"
    )
    benchmark_suite_id: Optional[str] = Field(
        None, description="Benchmark suite identifier for grouping related runs"
    )
    model_version: Optional[str] = Field(
        None, description="Model version or identifier (e.g., 'gpt-4-0125-preview')"
    )
    timestamp: datetime = Field(..., description="When the benchmark run started")
    property_results: Dict[str, PropertyExecutionResult] = Field(
        default_factory=dict,
        description="Results by property type (key: property_type)",
    )
    total_tasks: int = Field(
        ..., ge=0, description="Total tasks executed across all properties"
    )
    overall_average_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall average score (mean of all task final_scores)",
    )
    execution_time_seconds: float = Field(
        ..., ge=0.0, description="Total execution time in seconds"
    )

