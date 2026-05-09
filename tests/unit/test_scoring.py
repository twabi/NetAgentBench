"""
Unit tests for Scoring components.

These tests use mocked data for fast execution and focus on
the scoring logic and metric calculations.
"""
import pytest
from unittest.mock import Mock

from benchmark.models.results import PropertyEvaluationResult, ScoringResult, ValidityCheck
from benchmark.models.submission import Approach, CommandSequence
from benchmark.models.task import TaskDefinition, OptimalSolution, Platform
from benchmark.executor.command import ExecutionLogEntry
from datetime import datetime

# Import scoring components (will fail until implemented)
try:
    from benchmark.scoring.metrics import ScoringCalculator
    from benchmark.scoring.validity import ValidityChecker
except ImportError:
    ScoringCalculator = None
    ValidityChecker = None


@pytest.mark.skipif(ScoringCalculator is None, reason="ScoringCalculator not implemented yet")
class TestCompletenessMetric:
    """Tests for completeness score calculation"""

    def test_completeness_all_satisfied(self):
        """Test completeness when all properties are satisfied"""
        calculator = ScoringCalculator()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop2",
                satisfied=True,
                observation_raw="output2",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop3",
                satisfied=True,
                observation_raw="output3",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        completeness = calculator.compute_completeness(property_results)
        
        assert completeness == 1.0

    def test_completeness_none_satisfied(self):
        """Test completeness when no properties are satisfied"""
        calculator = ScoringCalculator()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=False,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop2",
                satisfied=False,
                observation_raw="output2",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        completeness = calculator.compute_completeness(property_results)
        
        assert completeness == 0.0

    def test_completeness_partial(self):
        """Test completeness with partial satisfaction"""
        calculator = ScoringCalculator()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop2",
                satisfied=False,
                observation_raw="output2",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop3",
                satisfied=True,
                observation_raw="output3",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop4",
                satisfied=False,
                observation_raw="output4",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        completeness = calculator.compute_completeness(property_results)
        
        # 2 out of 4 satisfied = 0.5
        assert completeness == 0.5

    def test_completeness_empty_list(self):
        """Test completeness with empty property list"""
        calculator = ScoringCalculator()
        
        property_results = []
        
        completeness = calculator.compute_completeness(property_results)
        
        # Convention: 0 properties = 0.0 completeness (or could be 1.0, depends on interpretation)
        assert completeness == 0.0


@pytest.mark.skipif(ScoringCalculator is None, reason="ScoringCalculator not implemented yet")
class TestRobustnessMetric:
    """Tests for robustness score calculation"""

    def test_robustness_complete_solution(self):
        """Test robustness for complete solution (MVP: 1.0 if complete)"""
        calculator = ScoringCalculator()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        robustness = calculator.compute_robustness(property_results)
        
        # MVP: 1.0 if completeness = 1.0
        assert robustness == 1.0

    def test_robustness_incomplete_solution(self):
        """Test robustness for incomplete solution (MVP: 0.0 if not complete)"""
        calculator = ScoringCalculator()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop2",
                satisfied=False,
                observation_raw="output2",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        robustness = calculator.compute_robustness(property_results)
        
        # MVP: 0.0 if not complete
        assert robustness == 0.0


@pytest.mark.skipif(ScoringCalculator is None, reason="ScoringCalculator not implemented yet")
class TestSyntacticValidityMetric:
    """Tests for syntactic validity score calculation"""

    def test_syntactic_validity_all_successful(self):
        """Test syntactic validity when all commands succeed"""
        calculator = ScoringCalculator()
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=True,
                stdout="output1",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd2",
                success=True,
                stdout="output2",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
        ]
        
        syntactic_validity = calculator.compute_syntactic_validity(execution_log)
        
        assert syntactic_validity == 1.0

    def test_syntactic_validity_all_failed(self):
        """Test syntactic validity when all commands fail"""
        calculator = ScoringCalculator()
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=False,
                stdout="",
                stderr="error1",
                exit_code=1,
                execution_time=0.1,
                error="Command failed"
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd2",
                success=False,
                stdout="",
                stderr="error2",
                exit_code=1,
                execution_time=0.1,
                error="Command failed"
            ),
        ]
        
        syntactic_validity = calculator.compute_syntactic_validity(execution_log)
        
        assert syntactic_validity == 0.0

    def test_syntactic_validity_partial(self):
        """Test syntactic validity with partial success"""
        calculator = ScoringCalculator()
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=True,
                stdout="output1",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd2",
                success=False,
                stdout="",
                stderr="error2",
                exit_code=1,
                execution_time=0.1,
                error="Command failed"
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd3",
                success=True,
                stdout="output3",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
        ]
        
        syntactic_validity = calculator.compute_syntactic_validity(execution_log)
        
        # 2 out of 3 successful = 0.666...
        assert abs(syntactic_validity - 0.6666666666666666) < 0.0001

    def test_syntactic_validity_empty_log(self):
        """Test syntactic validity with empty execution log"""
        calculator = ScoringCalculator()
        
        execution_log = []
        
        syntactic_validity = calculator.compute_syntactic_validity(execution_log)
        
        # Convention: 0 commands = 0.0 validity
        assert syntactic_validity == 0.0


@pytest.mark.skipif(ScoringCalculator is None, reason="ScoringCalculator not implemented yet")
class TestEfficiencyMetric:
    """Tests for efficiency score calculation"""

    def test_efficiency_with_optimal_solution(self):
        """Test efficiency when optimal solution is provided"""
        calculator = ScoringCalculator()
        
        approach = Approach(
            commands=[
                CommandSequence(node="node1", commands=["cmd1", "cmd2", "cmd3"])
            ]
        )
        
        optimal_solution = OptimalSolution(
            command_count=3,
            description="Optimal has 3 commands"
        )
        
        efficiency = calculator.compute_efficiency(approach, optimal_solution)
        
        # 3 optimal / 3 actual = 1.0
        assert efficiency == 1.0

    def test_efficiency_worse_than_optimal(self):
        """Test efficiency when solution uses more commands than optimal"""
        calculator = ScoringCalculator()
        
        approach = Approach(
            commands=[
                CommandSequence(node="node1", commands=["cmd1", "cmd2", "cmd3", "cmd4", "cmd5"])
            ]
        )
        
        optimal_solution = OptimalSolution(
            command_count=3,
            description="Optimal has 3 commands"
        )
        
        efficiency = calculator.compute_efficiency(approach, optimal_solution)
        
        # 3 optimal / 5 actual = 0.6
        assert efficiency == 0.6

    def test_efficiency_better_than_optimal(self):
        """Test efficiency when solution uses fewer commands (capped at 1.0)"""
        calculator = ScoringCalculator()
        
        approach = Approach(
            commands=[
                CommandSequence(node="node1", commands=["cmd1", "cmd2"])
            ]
        )
        
        optimal_solution = OptimalSolution(
            command_count=3,
            description="Optimal has 3 commands"
        )
        
        efficiency = calculator.compute_efficiency(approach, optimal_solution)
        
        # min(1, 3 / 2) = 1.0 (capped)
        assert efficiency == 1.0

    def test_efficiency_no_optimal_solution(self):
        """Test efficiency when no optimal solution is provided"""
        calculator = ScoringCalculator()
        
        approach = Approach(
            commands=[
                CommandSequence(node="node1", commands=["cmd1", "cmd2"])
            ]
        )
        
        efficiency = calculator.compute_efficiency(approach, None)
        
        # Should return None when no optimal solution
        assert efficiency is None

    def test_efficiency_multiple_nodes(self):
        """Test efficiency with commands on multiple nodes"""
        calculator = ScoringCalculator()
        
        approach = Approach(
            commands=[
                CommandSequence(node="node1", commands=["cmd1", "cmd2"]),
                CommandSequence(node="node2", commands=["cmd3", "cmd4", "cmd5"]),
            ]
        )
        
        optimal_solution = OptimalSolution(
            command_count=4,
            description="Optimal has 4 commands"
        )
        
        efficiency = calculator.compute_efficiency(approach, optimal_solution)
        
        # 4 optimal / 5 actual = 0.8
        assert efficiency == 0.8


@pytest.mark.skipif(ScoringCalculator is None, reason="ScoringCalculator not implemented yet")
class TestFinalScoreCalculation:
    """Tests for final score calculation with weights"""

    def test_final_score_default_weights_with_efficiency(self):
        """Test final score with default weights and efficiency"""
        calculator = ScoringCalculator()
        
        weights = {"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1}
        
        final_score = calculator.compute_final_score(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=1.0,
            weights=weights
        )
        
        # 0.4*1.0 + 0.3*1.0 + 0.2*1.0 + 0.1*1.0 = 1.0
        assert abs(final_score - 1.0) < 0.0001

    def test_final_score_default_weights_without_efficiency(self):
        """Test final score when efficiency is None (redistribute weight)"""
        calculator = ScoringCalculator()
        
        weights = {"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1}
        
        final_score = calculator.compute_final_score(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=None,
            weights=weights
        )
        
        # When efficiency is None, redistribute its weight (0.1) proportionally
        # Total without efficiency: 0.4 + 0.3 + 0.2 = 0.9
        # New weights: C=0.4/0.9, R=0.3/0.9, X=0.2/0.9
        # Score = (0.4/0.9)*1.0 + (0.3/0.9)*1.0 + (0.2/0.9)*1.0 = 1.0
        assert final_score == 1.0

    def test_final_score_partial_metrics(self):
        """Test final score with partial metric values"""
        calculator = ScoringCalculator()
        
        weights = {"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1}
        
        final_score = calculator.compute_final_score(
            completeness=0.5,
            robustness=0.8,
            syntactic_validity=0.9,
            efficiency=0.6,
            weights=weights
        )
        
        # 0.4*0.5 + 0.3*0.8 + 0.2*0.9 + 0.1*0.6 = 0.2 + 0.24 + 0.18 + 0.06 = 0.68
        assert abs(final_score - 0.68) < 0.0001

    def test_final_score_custom_weights(self):
        """Test final score with custom weights"""
        calculator = ScoringCalculator()
        
        # Equal weights
        weights = {"completeness": 0.25, "robustness": 0.25, "syntactic_validity": 0.25, "efficiency": 0.25}
        
        final_score = calculator.compute_final_score(
            completeness=1.0,
            robustness=0.0,
            syntactic_validity=1.0,
            efficiency=0.0,
            weights=weights
        )
        
        # 0.25*1.0 + 0.25*0.0 + 0.25*1.0 + 0.25*0.0 = 0.5
        assert final_score == 0.5

    def test_final_score_zero_metrics(self):
        """Test final score when all metrics are zero"""
        calculator = ScoringCalculator()
        
        weights = {"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1}
        
        final_score = calculator.compute_final_score(
            completeness=0.0,
            robustness=0.0,
            syntactic_validity=0.0,
            efficiency=0.0,
            weights=weights
        )
        
        assert final_score == 0.0


@pytest.mark.skipif(ScoringCalculator is None, reason="ScoringCalculator not implemented yet")
class TestComputeAllScores:
    """Tests for computing all scores together"""

    def test_compute_all_scores_complete_valid_solution(self):
        """Test computing all scores for a complete, valid solution"""
        calculator = ScoringCalculator()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=True,
                stdout="output1",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
        ]
        
        approach = Approach(
            commands=[
                CommandSequence(node="node1", commands=["cmd1"])
            ]
        )
        
        optimal_solution = OptimalSolution(command_count=1, description="Optimal")
        
        scoring_result = calculator.compute_all_scores(
            property_results=property_results,
            execution_log=execution_log,
            approach=approach,
            optimal_solution=optimal_solution
        )
        
        assert isinstance(scoring_result, ScoringResult)
        assert scoring_result.completeness == 1.0
        assert scoring_result.robustness == 1.0
        assert scoring_result.syntactic_validity == 1.0
        assert scoring_result.efficiency == 1.0
        assert scoring_result.final_score > 0.0
        assert "completeness" in scoring_result.weights

    def test_compute_all_scores_partial_solution(self):
        """Test computing all scores for a partial solution"""
        calculator = ScoringCalculator()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
            PropertyEvaluationResult(
                property_id="prop2",
                satisfied=False,
                observation_raw="output2",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=True,
                stdout="output1",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd2",
                success=False,
                stdout="",
                stderr="error",
                exit_code=1,
                execution_time=0.1,
                error="Failed"
            ),
        ]
        
        approach = Approach(
            commands=[
                CommandSequence(node="node1", commands=["cmd1", "cmd2"])
            ]
        )
        
        scoring_result = calculator.compute_all_scores(
            property_results=property_results,
            execution_log=execution_log,
            approach=approach,
            optimal_solution=None
        )
        
        assert scoring_result.completeness == 0.5
        assert scoring_result.robustness == 0.0  # MVP: 0 if not complete
        assert scoring_result.syntactic_validity == 0.5
        assert scoring_result.efficiency is None
        assert 0.0 < scoring_result.final_score < 1.0


@pytest.mark.skipif(ValidityChecker is None, reason="ValidityChecker not implemented yet")
class TestValidityChecker:
    """Tests for validity checking (Theorem 1)"""

    def test_validity_check_valid_solution(self):
        """Test validity check for a valid solution"""
        checker = ValidityChecker()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=True,
                stdout="output1",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
        ]
        
        validity = checker.check_validity(property_results, execution_log, final_score=1.0)
        
        assert isinstance(validity, ValidityCheck)
        assert validity.condition_a_syntactic is True
        assert validity.condition_b_semantic is True
        assert validity.is_valid_solution is True

    def test_validity_check_syntactic_error(self):
        """Test validity check when syntactic condition fails"""
        checker = ValidityChecker()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=False,
                stdout="",
                stderr="error",
                exit_code=1,
                execution_time=0.1,
                error="Syntax error"
            ),
        ]
        
        validity = checker.check_validity(property_results, execution_log)
        
        assert validity.condition_a_syntactic is False
        assert validity.condition_b_semantic is True
        assert validity.is_valid_solution is False

    def test_validity_check_semantic_error(self):
        """Test validity check when semantic condition fails"""
        checker = ValidityChecker()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=False,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=True,
                stdout="output1",
                stderr="",
                exit_code=0,
                execution_time=0.1
            ),
        ]
        
        validity = checker.check_validity(property_results, execution_log)
        
        assert validity.condition_a_syntactic is True
        assert validity.condition_b_semantic is False
        assert validity.is_valid_solution is False

    def test_validity_check_both_conditions_fail(self):
        """Test validity check when both conditions fail"""
        checker = ValidityChecker()
        
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=False,
                observation_raw="output1",
                observation_parsed=None,
                evaluation_time_seconds=0.1
            ),
        ]
        
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="node1",
                command="cmd1",
                success=False,
                stdout="",
                stderr="error",
                exit_code=1,
                execution_time=0.1,
                error="Failed"
            ),
        ]
        
        validity = checker.check_validity(property_results, execution_log)
        
        assert validity.condition_a_syntactic is False
        assert validity.condition_b_semantic is False
        assert validity.is_valid_solution is False

    def test_validity_check_empty_inputs(self):
        """Test validity check with empty property results and execution log"""
        checker = ValidityChecker()
        
        validity = checker.check_validity([], [])
        
        # Convention: empty means nothing to validate
        # Could be either valid or invalid depending on interpretation
        # Let's say: no properties = semantic success, no commands = syntactic success
        assert isinstance(validity, ValidityCheck)

