"""
Unit tests for analysis models.

Tests all Pydantic models used for benchmark analysis results.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from benchmark.models.analysis import (
    AggregateScores,
    AggregateExecutionMetrics,
    PropertyStats,
    TesteeAnalysis,
    ScoreComparison,
    TTestResult,
    ANOVAResult,
    StatisticalTestResults,
    PropertyComparison,
    ComparisonAnalysis,
    TesteePropertyStats,
    PropertyAnalysis,
    AnalysisResult,
)


class TestAggregateScores:
    """Test AggregateScores model"""

    def test_create_aggregate_scores(self):
        """Test creating aggregate scores"""
        scores = AggregateScores(
            completeness=0.8,
            robustness=0.7,
            syntactic_validity=0.9,
            efficiency=0.6,
            final_score=0.75,
        )
        assert scores.completeness == 0.8
        assert scores.robustness == 0.7
        assert scores.syntactic_validity == 0.9
        assert scores.efficiency == 0.6
        assert scores.final_score == 0.75

    def test_aggregate_scores_validation(self):
        """Test score validation (must be 0.0-1.0)"""
        with pytest.raises(ValidationError):
            AggregateScores(
                completeness=1.5,  # Invalid
                robustness=0.7,
                syntactic_validity=0.9,
                efficiency=0.6,
                final_score=0.75,
            )

    def test_aggregate_scores_optional_efficiency(self):
        """Test efficiency can be None"""
        scores = AggregateScores(
            completeness=0.8,
            robustness=0.7,
            syntactic_validity=0.9,
            efficiency=None,
            final_score=0.75,
        )
        assert scores.efficiency is None


class TestAggregateExecutionMetrics:
    """Test AggregateExecutionMetrics model"""

    def test_create_execution_metrics(self):
        """Test creating execution metrics"""
        metrics = AggregateExecutionMetrics(
            avg_infrastructure_provision_time=45.2,
            avg_config_execution_time=12.5,
            avg_convergence_time=30.0,
            avg_evaluation_time=5.3,
            avg_total_time=92.0,
        )
        assert metrics.avg_infrastructure_provision_time == 45.2
        assert metrics.avg_config_execution_time == 12.5


class TestPropertyStats:
    """Test PropertyStats model"""

    def test_create_property_stats(self):
        """Test creating property stats"""
        stats = PropertyStats(
            property_type="reachability",
            total_tasks=10,
            successful_tasks=8,
            aggregate_scores=AggregateScores(
                completeness=0.8,
                robustness=0.75,
                syntactic_validity=0.95,
                efficiency=None,
                final_score=0.82,
            ),
        )
        assert stats.property_type == "reachability"
        assert stats.total_tasks == 10
        assert stats.successful_tasks == 8


class TestTesteeAnalysis:
    """Test TesteeAnalysis model"""

    def test_create_testee_analysis(self):
        """Test creating testee analysis"""
        analysis = TesteeAnalysis(
            testee_id="gpt-4",
            testee_type="llm",
            total_runs=25,
            property_breakdown={
                "reachability": PropertyStats(
                    property_type="reachability",
                    total_tasks=10,
                    successful_tasks=8,
                    aggregate_scores=AggregateScores(
                        completeness=0.8,
                        robustness=0.75,
                        syntactic_validity=0.95,
                        efficiency=None,
                        final_score=0.82,
                    ),
                )
            },
            aggregate_scores=AggregateScores(
                completeness=0.85,
                robustness=0.80,
                syntactic_validity=0.95,
                efficiency=None,
                final_score=0.86,
            ),
            execution_metrics=AggregateExecutionMetrics(
                avg_infrastructure_provision_time=45.0,
                avg_config_execution_time=10.0,
                avg_convergence_time=30.0,
                avg_evaluation_time=5.0,
                avg_total_time=90.0,
            ),
        )
        assert analysis.testee_id == "gpt-4"
        assert analysis.testee_type == "llm"
        assert analysis.total_runs == 25
        assert len(analysis.property_breakdown) == 1

    def test_testee_analysis_json_serialization(self):
        """Test JSON serialization/deserialization"""
        analysis = TesteeAnalysis(
            testee_id="baseline",
            testee_type="baseline",
            total_runs=5,
            property_breakdown={},
            aggregate_scores=AggregateScores(
                completeness=0.5,
                robustness=0.5,
                syntactic_validity=1.0,
                efficiency=None,
                final_score=0.6,
            ),
            execution_metrics=AggregateExecutionMetrics(
                avg_infrastructure_provision_time=40.0,
                avg_config_execution_time=5.0,
                avg_convergence_time=30.0,
                avg_evaluation_time=4.0,
                avg_total_time=79.0,
            ),
        )
        
        # Serialize to dict
        data = analysis.model_dump()
        assert data["testee_id"] == "baseline"
        
        # Deserialize back
        restored = TesteeAnalysis(**data)
        assert restored.testee_id == analysis.testee_id
        assert restored.total_runs == analysis.total_runs


class TestTTestResult:
    """Test TTestResult model"""

    def test_create_ttest_result(self):
        """Test creating t-test result"""
        result = TTestResult(
            t_statistic=2.5,
            p_value=0.02,
            effect_size=0.8,
            confidence_interval=(0.1, 0.3),
            testee_a="gpt-4",
            testee_b="baseline",
            mean_diff=0.2,
        )
        assert result.t_statistic == 2.5
        assert result.p_value == 0.02
        assert result.effect_size == 0.8
        assert result.confidence_interval == (0.1, 0.3)


class TestANOVAResult:
    """Test ANOVAResult model"""

    def test_create_anova_result(self):
        """Test creating ANOVA result"""
        result = ANOVAResult(
            f_statistic=5.2,
            p_value=0.01,
            testees=["gpt-4", "claude", "baseline"],
            post_hoc_tests={
                "gpt-4_vs_baseline": {"p_value": 0.01, "mean_diff": 0.3},
                "claude_vs_baseline": {"p_value": 0.05, "mean_diff": 0.2},
            },
        )
        assert result.f_statistic == 5.2
        assert result.p_value == 0.01
        assert len(result.testees) == 3


class TestStatisticalTestResults:
    """Test StatisticalTestResults model"""

    def test_with_ttest(self):
        """Test statistical results with t-test"""
        results = StatisticalTestResults(
            test_type="t-test",
            ttest_result=TTestResult(
                t_statistic=2.5,
                p_value=0.02,
                effect_size=0.8,
                confidence_interval=(0.1, 0.3),
                testee_a="gpt-4",
                testee_b="baseline",
                mean_diff=0.2,
            ),
            anova_result=None,
        )
        assert results.test_type == "t-test"
        assert results.ttest_result is not None
        assert results.anova_result is None

    def test_with_anova(self):
        """Test statistical results with ANOVA"""
        results = StatisticalTestResults(
            test_type="anova",
            ttest_result=None,
            anova_result=ANOVAResult(
                f_statistic=5.2,
                p_value=0.01,
                testees=["gpt-4", "claude", "baseline"],
                post_hoc_tests={},
            ),
        )
        assert results.test_type == "anova"
        assert results.anova_result is not None
        assert results.ttest_result is None


class TestComparisonAnalysis:
    """Test ComparisonAnalysis model"""

    def test_create_comparison_analysis(self):
        """Test creating comparison analysis"""
        analysis = ComparisonAnalysis(
            testees=["gpt-4", "baseline"],
            total_runs_per_testee={"gpt-4": 10, "baseline": 10},
            score_comparison=ScoreComparison(
                testee_scores={
                    "gpt-4": AggregateScores(
                        completeness=0.8,
                        robustness=0.75,
                        syntactic_validity=0.95,
                        efficiency=None,
                        final_score=0.82,
                    ),
                    "baseline": AggregateScores(
                        completeness=0.5,
                        robustness=0.5,
                        syntactic_validity=1.0,
                        efficiency=None,
                        final_score=0.6,
                    ),
                },
                score_differences={
                    "completeness": 0.3,
                    "robustness": 0.25,
                    "syntactic_validity": -0.05,
                    "final_score": 0.22,
                },
            ),
            statistical_tests=StatisticalTestResults(
                test_type="t-test",
                ttest_result=TTestResult(
                    t_statistic=2.5,
                    p_value=0.02,
                    effect_size=0.8,
                    confidence_interval=(0.1, 0.3),
                    testee_a="gpt-4",
                    testee_b="baseline",
                    mean_diff=0.22,
                ),
                anova_result=None,
            ),
            property_breakdown={},
        )
        assert len(analysis.testees) == 2
        assert analysis.total_runs_per_testee["gpt-4"] == 10


class TestPropertyAnalysis:
    """Test PropertyAnalysis model"""

    def test_create_property_analysis(self):
        """Test creating property analysis"""
        analysis = PropertyAnalysis(
            property_type="reachability",
            total_runs=20,
            testee_breakdown={
                "gpt-4": TesteePropertyStats(
                    testee_id="gpt-4",
                    total_tasks=10,
                    successful_tasks=8,
                    aggregate_scores=AggregateScores(
                        completeness=0.8,
                        robustness=0.75,
                        syntactic_validity=0.95,
                        efficiency=None,
                        final_score=0.82,
                    ),
                )
            },
            task_difficulty={
                "reachability_linear_2n": 0.9,
                "reachability_linear_3n": 0.7,
            },
        )
        assert analysis.property_type == "reachability"
        assert analysis.total_runs == 20
        assert len(analysis.testee_breakdown) == 1


class TestAnalysisResult:
    """Test AnalysisResult model"""

    def test_create_testee_analysis_result(self):
        """Test creating analysis result for testee analysis"""
        result = AnalysisResult(
            analysis_id="analysis_20251120_123456",
            analysis_type="testee",
            timestamp=datetime.now(),
            testee_analysis=TesteeAnalysis(
                testee_id="gpt-4",
                testee_type="llm",
                total_runs=10,
                property_breakdown={},
                aggregate_scores=AggregateScores(
                    completeness=0.8,
                    robustness=0.75,
                    syntactic_validity=0.95,
                    efficiency=None,
                    final_score=0.82,
                ),
                execution_metrics=AggregateExecutionMetrics(
                    avg_infrastructure_provision_time=45.0,
                    avg_config_execution_time=10.0,
                    avg_convergence_time=30.0,
                    avg_evaluation_time=5.0,
                    avg_total_time=90.0,
                ),
            ),
            comparison_analysis=None,
            property_analysis=None,
            export_paths={},
        )
        assert result.analysis_type == "testee"
        assert result.testee_analysis is not None
        assert result.comparison_analysis is None

    def test_create_comparison_analysis_result(self):
        """Test creating analysis result for comparison"""
        result = AnalysisResult(
            analysis_id="analysis_20251120_123457",
            analysis_type="comparison",
            timestamp=datetime.now(),
            testee_analysis=None,
            comparison_analysis=ComparisonAnalysis(
                testees=["gpt-4", "baseline"],
                total_runs_per_testee={"gpt-4": 10, "baseline": 10},
                score_comparison=ScoreComparison(
                    testee_scores={},
                    score_differences={},
                ),
                statistical_tests=StatisticalTestResults(
                    test_type="t-test",
                    ttest_result=None,
                    anova_result=None,
                ),
                property_breakdown={},
            ),
            property_analysis=None,
            export_paths={},
        )
        assert result.analysis_type == "comparison"
        assert result.comparison_analysis is not None

    def test_analysis_result_json_serialization(self):
        """Test full JSON serialization"""
        result = AnalysisResult(
            analysis_id="test_analysis",
            analysis_type="testee",
            timestamp=datetime.now(),
            testee_analysis=TesteeAnalysis(
                testee_id="baseline",
                testee_type="baseline",
                total_runs=5,
                property_breakdown={},
                aggregate_scores=AggregateScores(
                    completeness=0.5,
                    robustness=0.5,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=0.6,
                ),
                execution_metrics=AggregateExecutionMetrics(
                    avg_infrastructure_provision_time=40.0,
                    avg_config_execution_time=5.0,
                    avg_convergence_time=30.0,
                    avg_evaluation_time=4.0,
                    avg_total_time=79.0,
                ),
            ),
            comparison_analysis=None,
            property_analysis=None,
            export_paths={"json": "/path/to/result.json"},
        )
        
        # Serialize to dict
        data = result.model_dump()
        assert data["analysis_id"] == "test_analysis"
        assert data["analysis_type"] == "testee"
        
        # Deserialize back
        restored = AnalysisResult(**data)
        assert restored.analysis_id == result.analysis_id

