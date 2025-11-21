"""
Unit tests for BenchmarkAnalyzer.

Tests testee analysis, comparison analysis, and property analysis.
"""
import pytest
import tempfile
from datetime import datetime

from benchmark.analysis.analyzer import BenchmarkAnalyzer
from benchmark.storage import ResultsStorage
from benchmark.models.results import (
    BenchmarkResult,
    ScoringResult,
    ValidityCheck,
    ExecutionMetrics,
    PropertyEvaluationResult,
)


def create_sample_result(
    run_id: str,
    task_id: str,
    testee_id: str,
    testee_type: str,
    final_score: float,
    completeness: float = None,
):
    """Helper to create sample benchmark result"""
    if completeness is None:
        completeness = final_score
    
    return BenchmarkResult(
        run_id=run_id,
        timestamp=datetime.now(),
        task_id=task_id,
        testee_id=testee_id,
        testee_type=testee_type,
        success=True,
        property_results=[],
        scoring=ScoringResult(
            completeness=completeness,
            robustness=final_score * 0.9,
            syntactic_validity=0.95,
            efficiency=None,
            final_score=final_score,
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


@pytest.fixture
def temp_storage_with_data():
    """Create storage with sample data for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = ResultsStorage(base_dir=temp_dir)
        
        # Create results for gpt-4
        storage.save_result(
            create_sample_result("run1", "reachability_linear_2n", "gpt-4", "llm", 0.85)
        )
        storage.save_result(
            create_sample_result("run2", "reachability_linear_3n", "gpt-4", "llm", 0.80)
        )
        storage.save_result(
            create_sample_result("run3", "bgp_2as_basic", "gpt-4", "llm", 0.90)
        )
        
        # Create results for baseline
        storage.save_result(
            create_sample_result("run4", "reachability_linear_2n", "baseline", "baseline", 0.55)
        )
        storage.save_result(
            create_sample_result("run5", "reachability_linear_3n", "baseline", "baseline", 0.50)
        )
        storage.save_result(
            create_sample_result("run6", "bgp_2as_basic", "baseline", "baseline", 0.60)
        )
        
        yield storage


class TestBenchmarkAnalyzer:
    """Test BenchmarkAnalyzer class"""

    def test_initialization(self, temp_storage_with_data):
        """Test creating BenchmarkAnalyzer"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        assert analyzer is not None
        assert analyzer.storage == temp_storage_with_data

    def test_analyze_testee(self, temp_storage_with_data):
        """Test analyzing a single testee"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        
        analysis = analyzer.analyze_testee("gpt-4")
        
        # Check structure
        assert analysis.testee_id == "gpt-4"
        assert analysis.testee_type == "llm"
        assert analysis.total_runs == 3
        
        # Check aggregate scores
        assert analysis.aggregate_scores.completeness > 0
        assert analysis.aggregate_scores.final_score > 0
        
        # Check property breakdown
        assert len(analysis.property_breakdown) >= 1
        
        # Check execution metrics
        assert analysis.execution_metrics.avg_total_time > 0

    def test_analyze_testee_nonexistent(self, temp_storage_with_data):
        """Test analyzing non-existent testee"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        
        with pytest.raises(ValueError):
            analyzer.analyze_testee("nonexistent-testee")

    def test_analyze_comparison_two_testees(self, temp_storage_with_data):
        """Test comparing two testees"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        
        analysis = analyzer.analyze_comparison(["gpt-4", "baseline"])
        
        # Check structure
        assert len(analysis.testees) == 2
        assert "gpt-4" in analysis.testees
        assert "baseline" in analysis.testees
        
        # Check runs per testee
        assert analysis.total_runs_per_testee["gpt-4"] == 3
        assert analysis.total_runs_per_testee["baseline"] == 3
        
        # Check score comparison
        assert "gpt-4" in analysis.score_comparison.testee_scores
        assert "baseline" in analysis.score_comparison.testee_scores
        
        # Check statistical tests
        assert analysis.statistical_tests.test_type == "t-test"
        assert analysis.statistical_tests.ttest_result is not None
        
        # GPT-4 should score higher than baseline
        gpt4_score = analysis.score_comparison.testee_scores["gpt-4"].final_score
        baseline_score = analysis.score_comparison.testee_scores["baseline"].final_score
        assert gpt4_score > baseline_score

    def test_analyze_comparison_three_testees(self):
        """Test comparing three testees (ANOVA)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create results for three testees on same tasks
            for testee, score_offset in [("gpt-4", 0.85), ("claude", 0.75), ("baseline", 0.55)]:
                storage.save_result(
                    create_sample_result("run_" + testee + "_1", "task1", testee, "llm", score_offset)
                )
                storage.save_result(
                    create_sample_result("run_" + testee + "_2", "task2", testee, "llm", score_offset + 0.05)
                )
            
            analyzer = BenchmarkAnalyzer(storage)
            analysis = analyzer.analyze_comparison(["gpt-4", "claude", "baseline"])
            
            # Check ANOVA was used
            assert analysis.statistical_tests.test_type == "anova"
            assert analysis.statistical_tests.anova_result is not None
            assert len(analysis.testees) == 3

    def test_analyze_comparison_no_matched_runs(self):
        """Test comparison when testees have no matched runs"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create results for different tasks
            storage.save_result(
                create_sample_result("run1", "task1", "gpt-4", "llm", 0.85)
            )
            storage.save_result(
                create_sample_result("run2", "task2", "baseline", "baseline", 0.55)
            )
            
            analyzer = BenchmarkAnalyzer(storage)
            
            # Should raise error - no matched runs
            with pytest.raises(ValueError):
                analyzer.analyze_comparison(["gpt-4", "baseline"])

    def test_analyze_property_type(self, temp_storage_with_data):
        """Test analyzing a property type"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        
        analysis = analyzer.analyze_property_type("reachability")
        
        # Check structure
        assert analysis.property_type == "reachability"
        assert analysis.total_runs > 0
        
        # Check testee breakdown
        assert len(analysis.testee_breakdown) > 0
        assert "gpt-4" in analysis.testee_breakdown or "baseline" in analysis.testee_breakdown
        
        # Check task difficulty
        assert len(analysis.task_difficulty) > 0

    def test_analyze_property_type_nonexistent(self, temp_storage_with_data):
        """Test analyzing non-existent property type"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        
        with pytest.raises(ValueError):
            analyzer.analyze_property_type("nonexistent_property")

    def test_property_breakdown_aggregation(self, temp_storage_with_data):
        """Test that property breakdown is correctly aggregated"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        
        analysis = analyzer.analyze_testee("gpt-4")
        
        # Should have at least reachability and bgp properties
        assert len(analysis.property_breakdown) >= 1
        
        # Check that totals match
        total_from_breakdown = sum(
            stats.total_tasks for stats in analysis.property_breakdown.values()
        )
        assert total_from_breakdown <= analysis.total_runs

    def test_execution_metrics_aggregation(self, temp_storage_with_data):
        """Test that execution metrics are correctly averaged"""
        analyzer = BenchmarkAnalyzer(temp_storage_with_data)
        
        analysis = analyzer.analyze_testee("gpt-4")
        
        # Check all metrics are present and reasonable
        assert analysis.execution_metrics.avg_infrastructure_provision_time > 0
        assert analysis.execution_metrics.avg_config_execution_time >= 0
        assert analysis.execution_metrics.avg_convergence_time >= 0
        assert analysis.execution_metrics.avg_evaluation_time >= 0
        assert analysis.execution_metrics.avg_total_time > 0


class TestAnalyzerEdgeCases:
    """Test edge cases in analysis"""

    def test_single_run_testee(self):
        """Test analyzing testee with single run"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            storage.save_result(
                create_sample_result("run1", "task1", "gpt-4", "llm", 0.85)
            )
            
            analyzer = BenchmarkAnalyzer(storage)
            analysis = analyzer.analyze_testee("gpt-4")
            
            assert analysis.total_runs == 1
            assert analysis.aggregate_scores.final_score == 0.85

    def test_comparison_identical_scores(self):
        """Test comparison when testees have identical scores"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create identical results
            storage.save_result(
                create_sample_result("run1", "task1", "testee_a", "llm", 0.80)
            )
            storage.save_result(
                create_sample_result("run2", "task1", "testee_b", "llm", 0.80)
            )
            
            analyzer = BenchmarkAnalyzer(storage)
            analysis = analyzer.analyze_comparison(["testee_a", "testee_b"])
            
            # P-value should be high (no significant difference)
            assert analysis.statistical_tests.ttest_result.p_value > 0.5
            
            # Mean difference should be near zero
            assert abs(analysis.statistical_tests.ttest_result.mean_diff) < 0.01

    def test_task_difficulty_calculation(self):
        """Test task difficulty calculation in property analysis"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Task 1: easy (high scores)
            storage.save_result(
                create_sample_result("run1", "reachability_easy", "gpt-4", "llm", 0.95)
            )
            storage.save_result(
                create_sample_result("run2", "reachability_easy", "baseline", "baseline", 0.90)
            )
            
            # Task 2: hard (low scores)
            storage.save_result(
                create_sample_result("run3", "reachability_hard", "gpt-4", "llm", 0.50)
            )
            storage.save_result(
                create_sample_result("run4", "reachability_hard", "baseline", "baseline", 0.45)
            )
            
            analyzer = BenchmarkAnalyzer(storage)
            analysis = analyzer.analyze_property_type("reachability")
            
            # Easy task should have higher average score
            assert analysis.task_difficulty["reachability_easy"] > analysis.task_difficulty["reachability_hard"]

