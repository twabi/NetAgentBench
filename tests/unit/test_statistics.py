"""
Unit tests for statistical analysis functions.

Tests t-tests, ANOVA, confidence intervals, and effect sizes.
"""
import pytest
from benchmark.analysis.statistics import StatisticalAnalyzer
from benchmark.models.results import BenchmarkResult, ScoringResult, ValidityCheck, ExecutionMetrics
from datetime import datetime


@pytest.fixture
def sample_results_group_a():
    """Create sample benchmark results for group A (scores: 0.8, 0.85, 0.75, 0.9, 0.82)"""
    results = []
    scores = [0.8, 0.85, 0.75, 0.9, 0.82]
    
    for i, score in enumerate(scores):
        result = BenchmarkResult(
            run_id=f"run_a_{i}",
            timestamp=datetime.now(),
            task_id=f"task_{i}",
            testee_id="testee_a",
            testee_type="llm",
            success=True,
            property_results=[],
            scoring=ScoringResult(
                completeness=score,
                robustness=score,
                syntactic_validity=1.0,
                efficiency=None,
                final_score=score,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=40.0,
                config_execution_time=10.0,
                convergence_time=30.0,
                evaluation_time=5.0,
                total_time=85.0,
            ),
            execution_log=[],
            errors=[],
        )
        results.append(result)
    
    return results


@pytest.fixture
def sample_results_group_b():
    """Create sample benchmark results for group B (scores: 0.5, 0.55, 0.45, 0.6, 0.52)"""
    results = []
    scores = [0.5, 0.55, 0.45, 0.6, 0.52]
    
    for i, score in enumerate(scores):
        result = BenchmarkResult(
            run_id=f"run_b_{i}",
            timestamp=datetime.now(),
            task_id=f"task_{i}",
            testee_id="testee_b",
            testee_type="baseline",
            success=True,
            property_results=[],
            scoring=ScoringResult(
                completeness=score,
                robustness=score,
                syntactic_validity=1.0,
                efficiency=None,
                final_score=score,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=40.0,
                config_execution_time=10.0,
                convergence_time=30.0,
                evaluation_time=5.0,
                total_time=85.0,
            ),
            execution_log=[],
            errors=[],
        )
        results.append(result)
    
    return results


@pytest.fixture
def sample_results_group_c():
    """Create sample benchmark results for group C (scores: 0.65, 0.7, 0.6, 0.75, 0.68)"""
    results = []
    scores = [0.65, 0.7, 0.6, 0.75, 0.68]
    
    for i, score in enumerate(scores):
        result = BenchmarkResult(
            run_id=f"run_c_{i}",
            timestamp=datetime.now(),
            task_id=f"task_{i}",
            testee_id="testee_c",
            testee_type="human",
            success=True,
            property_results=[],
            scoring=ScoringResult(
                completeness=score,
                robustness=score,
                syntactic_validity=1.0,
                efficiency=None,
                final_score=score,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=40.0,
                config_execution_time=10.0,
                convergence_time=30.0,
                evaluation_time=5.0,
                total_time=85.0,
            ),
            execution_log=[],
            errors=[],
        )
        results.append(result)
    
    return results


class TestStatisticalAnalyzer:
    """Test StatisticalAnalyzer class"""

    def test_initialization(self):
        """Test creating StatisticalAnalyzer"""
        analyzer = StatisticalAnalyzer()
        assert analyzer is not None

    def test_compare_two_testees(self, sample_results_group_a, sample_results_group_b):
        """Test t-test comparison between two testees"""
        analyzer = StatisticalAnalyzer()
        
        result = analyzer.compare_two_testees(
            sample_results_group_a,
            sample_results_group_b,
            "testee_a",
            "testee_b"
        )
        
        # Check result structure
        assert result.testee_a == "testee_a"
        assert result.testee_b == "testee_b"
        assert isinstance(result.t_statistic, float)
        assert isinstance(result.p_value, float)
        assert 0.0 <= result.p_value <= 1.0
        assert isinstance(result.effect_size, float)
        assert isinstance(result.confidence_interval, tuple)
        assert len(result.confidence_interval) == 2
        assert isinstance(result.mean_diff, float)
        
        # Group A (mean ~0.824) should score higher than Group B (mean ~0.524)
        assert result.mean_diff > 0.25  # Approximately 0.3

    def test_compare_multiple_testees(
        self, sample_results_group_a, sample_results_group_b, sample_results_group_c
    ):
        """Test ANOVA comparison for multiple testees"""
        analyzer = StatisticalAnalyzer()
        
        testee_runs = {
            "testee_a": sample_results_group_a,
            "testee_b": sample_results_group_b,
            "testee_c": sample_results_group_c,
        }
        
        result = analyzer.compare_multiple_testees(testee_runs)
        
        # Check result structure
        assert result.f_statistic >= 0.0
        assert isinstance(result.p_value, float)
        assert 0.0 <= result.p_value <= 1.0
        assert len(result.testees) == 3
        assert "testee_a" in result.testees
        assert "testee_b" in result.testees
        assert "testee_c" in result.testees
        assert isinstance(result.post_hoc_tests, dict)

    def test_compute_confidence_interval(self, sample_results_group_a):
        """Test confidence interval calculation"""
        analyzer = StatisticalAnalyzer()
        
        scores = [r.scoring.final_score for r in sample_results_group_a]
        ci_lower, ci_upper = analyzer.compute_confidence_interval(scores, confidence=0.95)
        
        # Check bounds
        assert isinstance(ci_lower, float)
        assert isinstance(ci_upper, float)
        assert ci_lower < ci_upper
        
        # CI should contain the mean
        mean_score = sum(scores) / len(scores)
        assert ci_lower <= mean_score <= ci_upper

    def test_compute_effect_size(self, sample_results_group_a, sample_results_group_b):
        """Test Cohen's d effect size calculation"""
        analyzer = StatisticalAnalyzer()
        
        scores_a = [r.scoring.final_score for r in sample_results_group_a]
        scores_b = [r.scoring.final_score for r in sample_results_group_b]
        
        effect_size = analyzer.compute_effect_size(scores_a, scores_b)
        
        # Effect size should be a float
        assert isinstance(effect_size, float)
        
        # Given the large difference between groups, effect size should be large
        assert abs(effect_size) > 1.0  # Large effect

    def test_empty_data_handling(self):
        """Test handling of empty data"""
        analyzer = StatisticalAnalyzer()
        
        # Empty scores should raise ValueError or return None
        with pytest.raises((ValueError, ZeroDivisionError)):
            analyzer.compute_confidence_interval([], confidence=0.95)

    def test_single_value_data(self):
        """Test handling of single data point"""
        analyzer = StatisticalAnalyzer()
        
        # Single score should handle gracefully
        try:
            ci_lower, ci_upper = analyzer.compute_confidence_interval([0.5], confidence=0.95)
            # If it doesn't raise, check that interval makes sense
            assert ci_lower <= 0.5 <= ci_upper
        except (ValueError, ZeroDivisionError):
            # It's acceptable to raise an error for insufficient data
            pass

    def test_identical_groups(self, sample_results_group_a):
        """Test comparison of identical groups (should show no difference)"""
        analyzer = StatisticalAnalyzer()
        
        # Compare group A with itself
        result = analyzer.compare_two_testees(
            sample_results_group_a,
            sample_results_group_a,
            "testee_a",
            "testee_a"
        )
        
        # Mean difference should be 0
        assert abs(result.mean_diff) < 0.001
        # P-value should be very high (no significant difference)
        assert result.p_value > 0.5

    def test_confidence_interval_90_percent(self, sample_results_group_a):
        """Test confidence interval with different confidence level"""
        analyzer = StatisticalAnalyzer()
        
        scores = [r.scoring.final_score for r in sample_results_group_a]
        ci_90_lower, ci_90_upper = analyzer.compute_confidence_interval(scores, confidence=0.90)
        ci_95_lower, ci_95_upper = analyzer.compute_confidence_interval(scores, confidence=0.95)
        
        # 95% CI should be wider than 90% CI
        ci_90_width = ci_90_upper - ci_90_lower
        ci_95_width = ci_95_upper - ci_95_lower
        assert ci_95_width > ci_90_width

    def test_effect_size_zero(self):
        """Test effect size when groups are identical"""
        analyzer = StatisticalAnalyzer()
        
        scores = [0.8, 0.8, 0.8, 0.8, 0.8]
        effect_size = analyzer.compute_effect_size(scores, scores)
        
        # Effect size should be 0 or very close to 0
        assert abs(effect_size) < 0.001


class TestStatisticsEdgeCases:
    """Test edge cases in statistical analysis"""

    def test_very_small_sample_ttest(self):
        """Test t-test with very small sample (n=2)"""
        analyzer = StatisticalAnalyzer()
        
        results_a = []
        results_b = []
        
        for i, score in enumerate([0.9, 0.85]):
            results_a.append(BenchmarkResult(
                run_id=f"run_a_{i}",
                timestamp=datetime.now(),
                task_id=f"task_{i}",
                testee_id="testee_a",
                testee_type="llm",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=score,
                    robustness=score,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=score,
                    weights={},
                ),
                validity=ValidityCheck(
                    is_valid_solution=True,
                    condition_a_syntactic=True,
                    condition_b_semantic=True,
                ),
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=40.0,
                    config_execution_time=10.0,
                    convergence_time=30.0,
                    evaluation_time=5.0,
                    total_time=85.0,
                ),
                execution_log=[],
                errors=[],
            ))
        
        for i, score in enumerate([0.5, 0.45]):
            results_b.append(BenchmarkResult(
                run_id=f"run_b_{i}",
                timestamp=datetime.now(),
                task_id=f"task_{i}",
                testee_id="testee_b",
                testee_type="baseline",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=score,
                    robustness=score,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=score,
                    weights={},
                ),
                validity=ValidityCheck(
                    is_valid_solution=True,
                    condition_a_syntactic=True,
                    condition_b_semantic=True,
                ),
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=40.0,
                    config_execution_time=10.0,
                    convergence_time=30.0,
                    evaluation_time=5.0,
                    total_time=85.0,
                ),
                execution_log=[],
                errors=[],
            ))
        
        # Should work even with small sample
        result = analyzer.compare_two_testees(results_a, results_b, "testee_a", "testee_b")
        assert isinstance(result.t_statistic, float)
        assert isinstance(result.p_value, float)

    def test_large_variance_groups(self):
        """Test t-test with groups having very different variances"""
        analyzer = StatisticalAnalyzer()
        
        # Group A: low variance (all similar scores)
        results_a = []
        for i, score in enumerate([0.80, 0.81, 0.82, 0.79, 0.80]):
            results_a.append(BenchmarkResult(
                run_id=f"run_a_{i}",
                timestamp=datetime.now(),
                task_id=f"task_{i}",
                testee_id="testee_a",
                testee_type="llm",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=score,
                    robustness=score,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=score,
                    weights={},
                ),
                validity=ValidityCheck(
                    is_valid_solution=True,
                    condition_a_syntactic=True,
                    condition_b_semantic=True,
                ),
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=40.0,
                    config_execution_time=10.0,
                    convergence_time=30.0,
                    evaluation_time=5.0,
                    total_time=85.0,
                ),
                execution_log=[],
                errors=[],
            ))
        
        # Group B: high variance (very different scores)
        results_b = []
        for i, score in enumerate([0.1, 0.9, 0.2, 0.8, 0.5]):
            results_b.append(BenchmarkResult(
                run_id=f"run_b_{i}",
                timestamp=datetime.now(),
                task_id=f"task_{i}",
                testee_id="testee_b",
                testee_type="baseline",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=score,
                    robustness=score,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=score,
                    weights={},
                ),
                validity=ValidityCheck(
                    is_valid_solution=True,
                    condition_a_syntactic=True,
                    condition_b_semantic=True,
                ),
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=40.0,
                    config_execution_time=10.0,
                    convergence_time=30.0,
                    evaluation_time=5.0,
                    total_time=85.0,
                ),
                execution_log=[],
                errors=[],
            ))
        
        # Should handle different variances
        result = analyzer.compare_two_testees(results_a, results_b, "testee_a", "testee_b")
        assert isinstance(result.t_statistic, float)
        assert isinstance(result.p_value, float)

