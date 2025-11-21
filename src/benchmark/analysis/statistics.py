"""
Statistical analysis functions for benchmark results.

Provides t-tests, ANOVA, confidence intervals, and effect size calculations
for comparing benchmark testees and analyzing performance.
"""
from typing import Dict, List, Tuple
import numpy as np
from scipy import stats

from benchmark.models.results import BenchmarkResult
from benchmark.models.analysis import TTestResult, ANOVAResult


class StatisticalAnalyzer:
    """Statistical analysis for benchmark results"""

    def compare_two_testees(
        self,
        runs_a: List[BenchmarkResult],
        runs_b: List[BenchmarkResult],
        testee_a: str,
        testee_b: str,
    ) -> TTestResult:
        """
        Perform independent samples t-test comparing two testees.

        Args:
            runs_a: Benchmark results for testee A
            runs_b: Benchmark results for testee B
            testee_a: ID of testee A
            testee_b: ID of testee B

        Returns:
            TTestResult with t-statistic, p-value, effect size, and confidence interval

        Raises:
            ValueError: If either group has insufficient data
        """
        if not runs_a or not runs_b:
            raise ValueError("Both groups must have at least one result")

        # Extract final scores
        scores_a = np.array([r.scoring.final_score for r in runs_a])
        scores_b = np.array([r.scoring.final_score for r in runs_b])

        # Perform independent samples t-test
        t_statistic, p_value = stats.ttest_ind(scores_a, scores_b)
        
        # Handle NaN values (insufficient variance)
        if np.isnan(t_statistic):
            t_statistic = 0.0
        if np.isnan(p_value):
            p_value = 1.0  # No significant difference if variance is zero

        # Compute effect size (Cohen's d)
        effect_size = self.compute_effect_size(scores_a.tolist(), scores_b.tolist())

        # Compute mean difference
        mean_diff = float(np.mean(scores_a) - np.mean(scores_b))

        # Compute 95% confidence interval for mean difference
        # Using pooled standard error
        n_a = len(scores_a)
        n_b = len(scores_b)
        std_a = np.std(scores_a, ddof=1)
        std_b = np.std(scores_b, ddof=1)

        # Pooled standard error
        pooled_se = np.sqrt((std_a**2 / n_a) + (std_b**2 / n_b))

        # Degrees of freedom (Welch's approximation)
        df = ((std_a**2 / n_a + std_b**2 / n_b) ** 2) / (
            (std_a**2 / n_a) ** 2 / (n_a - 1) + (std_b**2 / n_b) ** 2 / (n_b - 1)
        )

        # Critical t-value for 95% CI
        t_critical = stats.t.ppf(0.975, df)

        # Confidence interval
        ci_lower = mean_diff - t_critical * pooled_se
        ci_upper = mean_diff + t_critical * pooled_se

        return TTestResult(
            t_statistic=float(t_statistic),
            p_value=float(p_value),
            effect_size=effect_size,
            confidence_interval=(float(ci_lower), float(ci_upper)),
            testee_a=testee_a,
            testee_b=testee_b,
            mean_diff=mean_diff,
        )

    def compare_multiple_testees(
        self, testee_runs: Dict[str, List[BenchmarkResult]]
    ) -> ANOVAResult:
        """
        Perform one-way ANOVA comparing multiple testees.

        Args:
            testee_runs: Dictionary mapping testee_id to list of BenchmarkResults

        Returns:
            ANOVAResult with F-statistic, p-value, and post-hoc tests

        Raises:
            ValueError: If fewer than 2 groups or any group is empty
        """
        if len(testee_runs) < 2:
            raise ValueError("Need at least 2 groups for ANOVA")

        testees = list(testee_runs.keys())
        score_groups = []

        for testee_id in testees:
            runs = testee_runs[testee_id]
            if not runs:
                raise ValueError(f"Testee {testee_id} has no results")
            scores = [r.scoring.final_score for r in runs]
            score_groups.append(scores)

        # Perform one-way ANOVA
        f_statistic, p_value = stats.f_oneway(*score_groups)

        # Perform post-hoc pairwise comparisons (Tukey HSD equivalent using t-tests)
        post_hoc_tests = {}
        for i, testee_a in enumerate(testees):
            for j, testee_b in enumerate(testees):
                if i < j:  # Only compare each pair once
                    key = f"{testee_a}_vs_{testee_b}"
                    
                    # Perform t-test for this pair
                    scores_a = score_groups[i]
                    scores_b = score_groups[j]
                    _, pairwise_p = stats.ttest_ind(scores_a, scores_b)
                    
                    # Mean difference
                    mean_a = np.mean(scores_a)
                    mean_b = np.mean(scores_b)
                    mean_diff = float(mean_a - mean_b)
                    
                    post_hoc_tests[key] = {
                        "p_value": float(pairwise_p),
                        "mean_diff": mean_diff,
                    }

        return ANOVAResult(
            f_statistic=float(f_statistic),
            p_value=float(p_value),
            testees=testees,
            post_hoc_tests=post_hoc_tests,
        )

    def compute_confidence_interval(
        self, scores: List[float], confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Compute confidence interval for mean score.

        Args:
            scores: List of scores
            confidence: Confidence level (default: 0.95 for 95% CI)

        Returns:
            Tuple of (lower_bound, upper_bound)

        Raises:
            ValueError: If scores list is empty
        """
        if not scores:
            raise ValueError("Cannot compute confidence interval for empty data")

        if len(scores) == 1:
            # For single value, return the value as both bounds
            return (scores[0], scores[0])

        scores_array = np.array(scores)
        mean = np.mean(scores_array)
        std_error = stats.sem(scores_array)
        
        # Degrees of freedom
        df = len(scores) - 1
        
        # Critical t-value
        alpha = 1 - confidence
        t_critical = stats.t.ppf(1 - alpha / 2, df)
        
        # Confidence interval
        margin_of_error = t_critical * std_error
        ci_lower = mean - margin_of_error
        ci_upper = mean + margin_of_error

        return (float(ci_lower), float(ci_upper))

    def compute_effect_size(self, group_a: List[float], group_b: List[float]) -> float:
        """
        Compute Cohen's d effect size.

        Cohen's d = (mean_a - mean_b) / pooled_std

        Args:
            group_a: Scores for group A
            group_b: Scores for group B

        Returns:
            Cohen's d effect size

        Raises:
            ValueError: If either group is empty
            ZeroDivisionError: If pooled standard deviation is zero
        """
        if not group_a or not group_b:
            raise ValueError("Both groups must have at least one value")

        scores_a = np.array(group_a)
        scores_b = np.array(group_b)

        mean_a = np.mean(scores_a)
        mean_b = np.mean(scores_b)
        
        # Calculate pooled standard deviation
        n_a = len(scores_a)
        n_b = len(scores_b)
        
        if n_a == 1 and n_b == 1:
            # Special case: both groups have single value
            # Return 0 if means are equal, otherwise infinity indicator
            if abs(mean_a - mean_b) < 1e-10:
                return 0.0
            # Return a large value to indicate infinite effect size
            return float('inf') if mean_a > mean_b else float('-inf')
        
        var_a = np.var(scores_a, ddof=1) if n_a > 1 else 0.0
        var_b = np.var(scores_b, ddof=1) if n_b > 1 else 0.0
        
        pooled_std = np.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))

        if pooled_std == 0:
            # If pooled std is 0, all values are identical
            if abs(mean_a - mean_b) < 1e-10:
                return 0.0
            else:
                # Non-zero difference but zero variance - shouldn't happen in practice
                raise ZeroDivisionError("Pooled standard deviation is zero")

        cohen_d = (mean_a - mean_b) / pooled_std

        return float(cohen_d)

