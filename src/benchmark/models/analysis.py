"""
Pydantic models for benchmark analysis results.

This module defines models for analyzing and comparing benchmark results,
including testee analysis, multi-testee comparisons, and property-type analysis.
"""
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# Aggregate Metrics Models
# ============================================================================


class AggregateScores(BaseModel):
    """Aggregate scoring metrics across multiple runs"""

    completeness: float = Field(
        ..., ge=0.0, le=1.0, description="Average completeness score"
    )
    robustness: float = Field(
        ..., ge=0.0, le=1.0, description="Average robustness score"
    )
    syntactic_validity: float = Field(
        ..., ge=0.0, le=1.0, description="Average syntactic validity score"
    )
    efficiency: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Average efficiency score (if available)"
    )
    final_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average final score"
    )


class AggregateExecutionMetrics(BaseModel):
    """
    Aggregate execution timing metrics across multiple runs.
    
    Multi-turn fields are optional and only populated when analyzing
    multi-turn benchmark runs.
    """

    avg_infrastructure_provision_time: float = Field(
        ..., ge=0.0, description="Average infrastructure provision time (seconds)"
    )
    avg_config_execution_time: float = Field(
        ..., ge=0.0, description="Average config execution time (seconds)"
    )
    avg_convergence_time: float = Field(
        ..., ge=0.0, description="Average convergence time (seconds)"
    )
    avg_evaluation_time: float = Field(
        ..., ge=0.0, description="Average evaluation time (seconds)"
    )
    avg_total_time: float = Field(
        ..., ge=0.0, description="Average total time (seconds)"
    )
    
    # Multi-turn specific aggregates
    avg_turns_to_complete: Optional[float] = Field(
        None, ge=0.0, description="Average number of config commands used (multi-turn only)"
    )
    avg_time_to_complete: Optional[float] = Field(
        None, ge=0.0, description="Average session duration in seconds (multi-turn only)"
    )
    termination_breakdown: Optional[Dict[str, int]] = Field(
        None, description="Count by termination reason: {'submitted': N, 'timeout': M, 'turn_limit': K}"
    )
    avg_tool_usage: Optional[Dict[str, float]] = Field(
        None, description="Average tool usage per session: {'exec_command': 10.5, 'get_nodes': 1.2}"
    )
    turn_success_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Fraction of multi-turn runs that succeeded"
    )


# ============================================================================
# Property-Level Statistics
# ============================================================================


class PropertyStats(BaseModel):
    """Statistics for a single property type"""

    property_type: str = Field(..., description="Property type identifier")
    total_tasks: int = Field(..., ge=0, description="Total tasks executed")
    successful_tasks: int = Field(..., ge=0, description="Tasks with valid solutions")
    aggregate_scores: AggregateScores = Field(
        ..., description="Aggregate scores for this property type"
    )


# ============================================================================
# Testee Analysis (Single Testee Performance)
# ============================================================================


class TesteeAnalysis(BaseModel):
    """Analysis of a single testee's performance across tasks"""

    testee_id: str = Field(..., description="Testee identifier")
    testee_type: str = Field(..., description="Type of testee (llm, human, baseline)")
    total_runs: int = Field(..., ge=0, description="Total number of runs")
    property_breakdown: Dict[str, PropertyStats] = Field(
        default_factory=dict,
        description="Performance breakdown by property type",
    )
    aggregate_scores: AggregateScores = Field(
        ..., description="Overall aggregate scores"
    )
    execution_metrics: AggregateExecutionMetrics = Field(
        ..., description="Overall execution metrics"
    )


# ============================================================================
# Statistical Test Results
# ============================================================================


class TTestResult(BaseModel):
    """Results of a two-sample t-test"""

    t_statistic: float = Field(..., description="T-statistic value")
    p_value: float = Field(..., ge=0.0, le=1.0, description="P-value")
    effect_size: float = Field(..., description="Cohen's d effect size")
    confidence_interval: Tuple[float, float] = Field(
        ..., description="95% confidence interval for mean difference"
    )
    testee_a: str = Field(..., description="First testee ID")
    testee_b: str = Field(..., description="Second testee ID")
    mean_diff: float = Field(..., description="Mean score difference (A - B)")


class ANOVAResult(BaseModel):
    """Results of ANOVA test for multiple groups"""

    f_statistic: float = Field(..., description="F-statistic value")
    p_value: float = Field(..., ge=0.0, le=1.0, description="P-value")
    testees: List[str] = Field(..., description="List of testee IDs compared")
    post_hoc_tests: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Post-hoc pairwise comparisons (e.g., Tukey HSD)",
    )


class StatisticalTestResults(BaseModel):
    """Statistical test results (either t-test or ANOVA)"""

    test_type: str = Field(..., description="Type of test: 't-test' or 'anova'")
    ttest_result: Optional[TTestResult] = Field(
        None, description="T-test result (if test_type is 't-test')"
    )
    anova_result: Optional[ANOVAResult] = Field(
        None, description="ANOVA result (if test_type is 'anova')"
    )


# ============================================================================
# Comparison Analysis (Multiple Testees)
# ============================================================================


class ScoreComparison(BaseModel):
    """Score comparison between multiple testees"""

    testee_scores: Dict[str, AggregateScores] = Field(
        default_factory=dict,
        description="Aggregate scores per testee",
    )
    score_differences: Dict[str, float] = Field(
        default_factory=dict,
        description="Score differences between testees (for specific metrics)",
    )


class PropertyComparison(BaseModel):
    """Comparison of testees on a specific property type"""

    property_type: str = Field(..., description="Property type identifier")
    testee_stats: Dict[str, PropertyStats] = Field(
        default_factory=dict,
        description="Stats per testee for this property",
    )
    statistical_tests: Optional[StatisticalTestResults] = Field(
        None, description="Statistical test results for this property"
    )


class ComparisonAnalysis(BaseModel):
    """Statistical comparison between multiple testees"""

    testees: List[str] = Field(..., description="List of testee IDs being compared")
    total_runs_per_testee: Dict[str, int] = Field(
        default_factory=dict,
        description="Number of runs per testee",
    )
    score_comparison: ScoreComparison = Field(
        ..., description="Overall score comparison"
    )
    statistical_tests: StatisticalTestResults = Field(
        ..., description="Overall statistical test results"
    )
    property_breakdown: Dict[str, PropertyComparison] = Field(
        default_factory=dict,
        description="Per-property comparison breakdown",
    )


# ============================================================================
# Property Analysis (Single Property Across Testees)
# ============================================================================


class TesteePropertyStats(BaseModel):
    """Statistics for a single testee on a specific property type"""

    testee_id: str = Field(..., description="Testee identifier")
    total_tasks: int = Field(..., ge=0, description="Total tasks executed")
    successful_tasks: int = Field(..., ge=0, description="Tasks with valid solutions")
    aggregate_scores: AggregateScores = Field(
        ..., description="Aggregate scores for this testee on this property"
    )


class PropertyAnalysis(BaseModel):
    """Analysis of all runs for a property type across testees"""

    property_type: str = Field(..., description="Property type identifier")
    total_runs: int = Field(..., ge=0, description="Total runs across all testees")
    testee_breakdown: Dict[str, TesteePropertyStats] = Field(
        default_factory=dict,
        description="Per-testee statistics for this property",
    )
    task_difficulty: Dict[str, float] = Field(
        default_factory=dict,
        description="Average score per task (task_id -> avg_score)",
    )


# ============================================================================
# Complete Analysis Result
# ============================================================================


class AnalysisResult(BaseModel):
    """Complete analysis output with all results and metadata"""

    analysis_id: str = Field(..., description="Unique identifier for this analysis")
    analysis_type: str = Field(
        ..., description="Type of analysis: 'testee', 'comparison', or 'property'"
    )
    timestamp: datetime = Field(..., description="When the analysis was performed")
    
    # One of these will be populated based on analysis_type
    testee_analysis: Optional[TesteeAnalysis] = Field(
        None, description="Testee analysis results (if type='testee')"
    )
    comparison_analysis: Optional[ComparisonAnalysis] = Field(
        None, description="Comparison analysis results (if type='comparison')"
    )
    property_analysis: Optional[PropertyAnalysis] = Field(
        None, description="Property analysis results (if type='property')"
    )
    
    export_paths: Dict[str, str] = Field(
        default_factory=dict,
        description="Paths to exported files (format -> file_path)",
    )

