"""
Main analysis engine for benchmark results.

Analyzes testees, compares multiple testees, and analyzes property types.
"""
from typing import Dict, List
from collections import defaultdict

from benchmark.storage import ResultsStorage
from benchmark.analysis.statistics import StatisticalAnalyzer
from benchmark.models.results import BenchmarkResult
from benchmark.models.analysis import (
    TesteeAnalysis,
    ComparisonAnalysis,
    PropertyAnalysis,
    AggregateScores,
    AggregateExecutionMetrics,
    PropertyStats,
    ScoreComparison,
    StatisticalTestResults,
    PropertyComparison,
    TesteePropertyStats,
)


class BenchmarkAnalyzer:
    """Main analysis engine for benchmark results"""

    def __init__(self, storage: ResultsStorage):
        """
        Initialize BenchmarkAnalyzer.

        Args:
            storage: ResultsStorage instance for loading results
        """
        self.storage = storage
        self.stats = StatisticalAnalyzer()

    def analyze_testee(self, testee_id: str) -> TesteeAnalysis:
        """
        Analyze all runs for a specific testee.

        Args:
            testee_id: Testee identifier

        Returns:
            TesteeAnalysis with aggregated metrics

        Raises:
            ValueError: If testee has no results
        """
        # Load all runs for this testee
        runs = self.storage.get_runs_by_testee(testee_id)

        if not runs:
            raise ValueError(f"No results found for testee: {testee_id}")

        # Determine testee type from first run
        testee_type = runs[0].testee_type

        # Group runs by property type (inferred from task_id)
        property_groups = self._group_by_property(runs)

        # Compute aggregate scores per property
        property_breakdown = {}
        for prop_type, prop_runs in property_groups.items():
            property_breakdown[prop_type] = self._compute_property_stats(
                prop_type, prop_runs
            )

        # Compute overall aggregate scores
        aggregate_scores = self._compute_aggregate_scores(runs)

        # Compute execution metrics
        execution_metrics = self._compute_execution_metrics(runs)

        return TesteeAnalysis(
            testee_id=testee_id,
            testee_type=testee_type,
            total_runs=len(runs),
            property_breakdown=property_breakdown,
            aggregate_scores=aggregate_scores,
            execution_metrics=execution_metrics,
        )

    def analyze_comparison(self, testee_ids: List[str]) -> ComparisonAnalysis:
        """
        Compare multiple testees statistically.

        Only compares runs on tasks that ALL testees have completed.

        Args:
            testee_ids: List of testee IDs to compare

        Returns:
            ComparisonAnalysis with comparison metrics and statistical tests

        Raises:
            ValueError: If fewer than 2 testees or no matched runs
        """
        if len(testee_ids) < 2:
            raise ValueError("Need at least 2 testees for comparison")

        # Get matched runs (only tasks completed by ALL testees)
        matched_runs = self.storage.get_matched_runs(testee_ids)

        if not matched_runs:
            raise ValueError(
                f"No matched runs found for testees: {testee_ids}. "
                "Testees must have completed the same tasks for comparison."
            )

        # Count total runs per testee (from matched runs only)
        total_runs_per_testee = {}
        for testee_id in testee_ids:
            total_runs_per_testee[testee_id] = len(matched_runs)

        # Compute aggregate scores per testee (from matched runs)
        testee_scores = {}
        testee_runs_dict = defaultdict(list)
        
        for task_id, task_results in matched_runs.items():
            for testee_id, result in task_results.items():
                testee_runs_dict[testee_id].append(result)
        
        for testee_id in testee_ids:
            runs = testee_runs_dict[testee_id]
            testee_scores[testee_id] = self._compute_aggregate_scores(runs)

        # Compute score differences (compare first testee to others)
        score_differences = {}
        if len(testee_ids) == 2:
            testee_a, testee_b = testee_ids[0], testee_ids[1]
            scores_a = testee_scores[testee_a]
            scores_b = testee_scores[testee_b]
            
            score_differences["completeness"] = scores_a.completeness - scores_b.completeness
            score_differences["robustness"] = scores_a.robustness - scores_b.robustness
            score_differences["syntactic_validity"] = scores_a.syntactic_validity - scores_b.syntactic_validity
            score_differences["final_score"] = scores_a.final_score - scores_b.final_score

        score_comparison = ScoreComparison(
            testee_scores=testee_scores,
            score_differences=score_differences,
        )

        # Perform statistical tests
        if len(testee_ids) == 2:
            # Two testees: t-test
            testee_a, testee_b = testee_ids[0], testee_ids[1]
            runs_a = testee_runs_dict[testee_a]
            runs_b = testee_runs_dict[testee_b]
            
            ttest_result = self.stats.compare_two_testees(
                runs_a, runs_b, testee_a, testee_b
            )
            
            statistical_tests = StatisticalTestResults(
                test_type="t-test",
                ttest_result=ttest_result,
                anova_result=None,
            )
        else:
            # Three or more testees: ANOVA
            anova_result = self.stats.compare_multiple_testees(testee_runs_dict)
            
            statistical_tests = StatisticalTestResults(
                test_type="anova",
                ttest_result=None,
                anova_result=anova_result,
            )

        # Property breakdown (compare on each property type)
        property_breakdown = self._compute_property_breakdown_comparison(
            testee_ids, testee_runs_dict
        )

        return ComparisonAnalysis(
            testees=testee_ids,
            total_runs_per_testee=total_runs_per_testee,
            score_comparison=score_comparison,
            statistical_tests=statistical_tests,
            property_breakdown=property_breakdown,
        )

    def analyze_property_type(self, property_type: str) -> PropertyAnalysis:
        """
        Analyze all runs for a property type across testees.

        Args:
            property_type: Property type identifier

        Returns:
            PropertyAnalysis with per-testee stats and task difficulty

        Raises:
            ValueError: If property type has no results
        """
        # Load all runs for this property type
        runs = self.storage.get_runs_by_property(property_type)

        if not runs:
            raise ValueError(f"No results found for property type: {property_type}")

        # Group by testee
        testee_groups = defaultdict(list)
        for run in runs:
            testee_groups[run.testee_id].append(run)

        # Compute per-testee stats
        testee_breakdown = {}
        for testee_id, testee_runs in testee_groups.items():
            testee_breakdown[testee_id] = TesteePropertyStats(
                testee_id=testee_id,
                total_tasks=len(testee_runs),
                successful_tasks=sum(1 for r in testee_runs if r.validity.is_valid_solution),
                aggregate_scores=self._compute_aggregate_scores(testee_runs),
            )

        # Compute task difficulty (average score per task across all testees)
        task_scores = defaultdict(list)
        for run in runs:
            task_scores[run.task_id].append(run.scoring.final_score)

        task_difficulty = {
            task_id: sum(scores) / len(scores)
            for task_id, scores in task_scores.items()
        }

        return PropertyAnalysis(
            property_type=property_type,
            total_runs=len(runs),
            testee_breakdown=testee_breakdown,
            task_difficulty=task_difficulty,
        )

    def _group_by_property(self, runs: List[BenchmarkResult]) -> Dict[str, List[BenchmarkResult]]:
        """Group runs by property type (inferred from task_id)"""
        property_groups = defaultdict(list)
        
        for run in runs:
            # Infer property type from task_id prefix
            task_id = run.task_id.lower()
            if task_id.startswith("reachability"):
                prop_type = "reachability"
            elif task_id.startswith("bgp"):
                prop_type = "bgp_configuration"
            elif task_id.startswith("ospf"):
                prop_type = "ospf_configuration"
            else:
                prop_type = "other"
            
            property_groups[prop_type].append(run)
        
        return dict(property_groups)

    def _compute_property_stats(
        self, property_type: str, runs: List[BenchmarkResult]
    ) -> PropertyStats:
        """Compute aggregate stats for a property type"""
        return PropertyStats(
            property_type=property_type,
            total_tasks=len(runs),
            successful_tasks=sum(1 for r in runs if r.validity.is_valid_solution),
            aggregate_scores=self._compute_aggregate_scores(runs),
        )

    def _compute_aggregate_scores(self, runs: List[BenchmarkResult]) -> AggregateScores:
        """Compute aggregate scores from a list of runs"""
        if not runs:
            raise ValueError("Cannot compute aggregate scores for empty runs")

        n = len(runs)
        
        completeness = sum(r.scoring.completeness for r in runs) / n
        robustness = sum(r.scoring.robustness for r in runs) / n
        syntactic_validity = sum(r.scoring.syntactic_validity for r in runs) / n
        
        # Efficiency may be None for some runs
        efficiency_values = [r.scoring.efficiency for r in runs if r.scoring.efficiency is not None]
        efficiency = sum(efficiency_values) / len(efficiency_values) if efficiency_values else None
        
        final_score = sum(r.scoring.final_score for r in runs) / n

        return AggregateScores(
            completeness=completeness,
            robustness=robustness,
            syntactic_validity=syntactic_validity,
            efficiency=efficiency,
            final_score=final_score,
        )

    def _compute_execution_metrics(
        self, runs: List[BenchmarkResult]
    ) -> AggregateExecutionMetrics:
        """Compute aggregate execution metrics from runs, including multi-turn aggregates."""
        if not runs:
            raise ValueError("Cannot compute execution metrics for empty runs")

        n = len(runs)
        
        # Base metrics (always computed)
        base_metrics = {
            "avg_infrastructure_provision_time": sum(r.metrics.infrastructure_provision_time for r in runs) / n,
            "avg_config_execution_time": sum(r.metrics.config_execution_time for r in runs) / n,
            "avg_convergence_time": sum(r.metrics.convergence_time for r in runs) / n,
            "avg_evaluation_time": sum(r.metrics.evaluation_time for r in runs) / n,
            "avg_total_time": sum(r.metrics.total_time for r in runs) / n,
        }
        
        # Multi-turn metrics (only computed if multi-turn runs exist)
        multi_turn_runs = [r for r in runs if r.metrics.is_multi_turn]
        
        if multi_turn_runs:
            mt_n = len(multi_turn_runs)
            
            # Average turns to complete
            turns_values = [r.metrics.turns_to_complete for r in multi_turn_runs if r.metrics.turns_to_complete is not None]
            avg_turns = sum(turns_values) / len(turns_values) if turns_values else None
            
            # Average time to complete
            time_values = [r.metrics.time_to_complete for r in multi_turn_runs if r.metrics.time_to_complete is not None]
            avg_time = sum(time_values) / len(time_values) if time_values else None
            
            # Termination breakdown
            termination_breakdown = {}
            for r in multi_turn_runs:
                if r.metrics.termination_reason:
                    reason = r.metrics.termination_reason
                    termination_breakdown[reason] = termination_breakdown.get(reason, 0) + 1
            
            # Average tool usage
            tool_usage_totals: Dict[str, float] = {}
            tool_usage_counts: Dict[str, int] = {}
            for r in multi_turn_runs:
                if r.metrics.tool_usage:
                    for tool, count in r.metrics.tool_usage.items():
                        tool_usage_totals[tool] = tool_usage_totals.get(tool, 0) + count
                        tool_usage_counts[tool] = tool_usage_counts.get(tool, 0) + 1
            avg_tool_usage = {
                tool: total / tool_usage_counts[tool]
                for tool, total in tool_usage_totals.items()
            } if tool_usage_totals else None
            
            # Turn success rate (fraction of multi-turn runs that succeeded)
            successful_mt = sum(1 for r in multi_turn_runs if r.success)
            turn_success_rate = successful_mt / mt_n if mt_n > 0 else None
            
            base_metrics.update({
                "avg_turns_to_complete": avg_turns,
                "avg_time_to_complete": avg_time,
                "termination_breakdown": termination_breakdown if termination_breakdown else None,
                "avg_tool_usage": avg_tool_usage,
                "turn_success_rate": turn_success_rate,
            })

        return AggregateExecutionMetrics(**base_metrics)

    def _compute_property_breakdown_comparison(
        self,
        testee_ids: List[str],
        testee_runs: Dict[str, List[BenchmarkResult]],
    ) -> Dict[str, PropertyComparison]:
        """Compute per-property comparison breakdown"""
        # Group runs by property type for each testee
        property_breakdown = {}
        
        # First, identify all property types present
        all_property_types = set()
        for runs in testee_runs.values():
            property_groups = self._group_by_property(runs)
            all_property_types.update(property_groups.keys())
        
        # For each property type, compute comparison
        for prop_type in all_property_types:
            # Get runs for this property from each testee
            testee_property_stats = {}
            property_runs_by_testee = {}
            
            for testee_id in testee_ids:
                runs = testee_runs[testee_id]
                property_groups = self._group_by_property(runs)
                
                if prop_type in property_groups:
                    prop_runs = property_groups[prop_type]
                    property_runs_by_testee[testee_id] = prop_runs
                    testee_property_stats[testee_id] = self._compute_property_stats(
                        prop_type, prop_runs
                    )
            
            # Compute statistical tests for this property if we have data
            statistical_tests = None
            if len(property_runs_by_testee) >= 2:
                testee_list = list(property_runs_by_testee.keys())
                if len(property_runs_by_testee) == 2:
                    # T-test
                    testee_a, testee_b = testee_list[0], testee_list[1]
                    ttest_result = self.stats.compare_two_testees(
                        property_runs_by_testee[testee_a],
                        property_runs_by_testee[testee_b],
                        testee_a,
                        testee_b,
                    )
                    statistical_tests = StatisticalTestResults(
                        test_type="t-test",
                        ttest_result=ttest_result,
                        anova_result=None,
                    )
                else:
                    # ANOVA
                    anova_result = self.stats.compare_multiple_testees(property_runs_by_testee)
                    statistical_tests = StatisticalTestResults(
                        test_type="anova",
                        ttest_result=None,
                        anova_result=anova_result,
                    )
            
            property_breakdown[prop_type] = PropertyComparison(
                property_type=prop_type,
                testee_stats=testee_property_stats,
                statistical_tests=statistical_tests,
            )
        
        return property_breakdown

