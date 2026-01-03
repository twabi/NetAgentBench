"""
Leaderboard Manager for benchmark results.

This module provides the LeaderboardManager class for creating, updating,
and persisting leaderboards based on benchmark results.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from benchmark.models.leaderboard import (
    LeaderboardEntry,
    Leaderboard,
    LeaderboardCollection,
)
from benchmark.models.results import BenchmarkRunResult, BenchmarkResult


# ============================================================================
# Standard Leaderboard Definitions
# ============================================================================


# Metrics to create leaderboards for
METRICS = ["overall", "completeness", "robustness", "syntactic_validity"]

# Property types to create per-property leaderboards for
PROPERTY_TYPES = ["reachability", "bgp_configuration", "ospf_configuration"]

# Evaluation modes
EVALUATION_MODES = ["single_turn", "multi_turn"]


def _create_standard_leaderboards() -> List[Leaderboard]:
    """
    Create the standard set of leaderboards.
    
    Creates:
    - Overall leaderboards (single-turn and multi-turn)
    - Per-metric leaderboards (completeness, robustness, syntactic_validity × modes)
    - Per-property leaderboards (reachability, BGP, OSPF × modes)
    
    Returns:
        List of initialized (empty) Leaderboard objects
    """
    leaderboards = []
    
    # Overall leaderboards
    for mode in EVALUATION_MODES:
        leaderboards.append(Leaderboard(
            leaderboard_id=f"overall_{mode}",
            name=f"Overall ({mode.replace('_', '-').title()})",
            description=f"Ranks testees by overall score in {mode.replace('_', '-')} mode",
            evaluation_mode=mode,
            metric_name="overall",
        ))
    
    # Per-metric leaderboards (excluding "overall" which was handled above)
    for metric in ["completeness", "robustness", "syntactic_validity"]:
        for mode in EVALUATION_MODES:
            leaderboards.append(Leaderboard(
                leaderboard_id=f"{metric}_{mode}",
                name=f"{metric.replace('_', ' ').title()} ({mode.replace('_', '-').title()})",
                description=f"Ranks testees by {metric.replace('_', ' ')} score in {mode.replace('_', '-')} mode",
                evaluation_mode=mode,
                metric_name=metric,
            ))
    
    # Per-property leaderboards
    for prop_type in PROPERTY_TYPES:
        for mode in EVALUATION_MODES:
            prop_name = prop_type.replace("_", " ").title()
            leaderboards.append(Leaderboard(
                leaderboard_id=f"{prop_type}_{mode}",
                name=f"{prop_name} ({mode.replace('_', '-').title()})",
                description=f"Ranks testees by overall score on {prop_name} tasks in {mode.replace('_', '-')} mode",
                evaluation_mode=mode,
                metric_name="overall",
                property_type=prop_type,
            ))
    
    return leaderboards


# ============================================================================
# Leaderboard Manager
# ============================================================================


class LeaderboardManager:
    """
    Manages leaderboard creation, updates, and persistence.
    
    Provides methods to:
    - Initialize standard leaderboards
    - Add benchmark run results to appropriate leaderboards
    - Save/load leaderboards to/from JSON files
    """

    def __init__(self, leaderboards_path: Optional[str] = None):
        """
        Initialize LeaderboardManager.
        
        Args:
            leaderboards_path: Path to leaderboards JSON file (optional).
                              If provided and exists, leaderboards will be loaded.
        """
        self._collection = LeaderboardCollection()
        self._path = Path(leaderboards_path) if leaderboards_path else None
        
        # Load existing leaderboards if path provided and file exists
        if self._path and self._path.exists():
            self.load_leaderboards(str(self._path))

    @property
    def collection(self) -> LeaderboardCollection:
        """Get the underlying LeaderboardCollection."""
        return self._collection

    def initialize_leaderboards(self) -> None:
        """
        Initialize all standard leaderboards.
        
        Creates empty leaderboards for:
        - Overall (single-turn and multi-turn)
        - Per-metric (completeness, robustness, syntactic_validity × modes)
        - Per-property (reachability, BGP, OSPF × modes)
        """
        for lb in _create_standard_leaderboards():
            self._collection.add_leaderboard(lb)

    def get_leaderboard(self, leaderboard_id: str) -> Optional[Leaderboard]:
        """
        Get a leaderboard by ID.
        
        Args:
            leaderboard_id: Leaderboard identifier
            
        Returns:
            Leaderboard or None if not found
        """
        return self._collection.get_leaderboard(leaderboard_id)

    def list_leaderboard_ids(self) -> List[str]:
        """
        List all leaderboard IDs.
        
        Returns:
            List of leaderboard IDs
        """
        return self._collection.list_leaderboard_ids()

    def add_benchmark_run(self, run_result: BenchmarkRunResult) -> List[str]:
        """
        Add a benchmark run result to all appropriate leaderboards.
        
        Determines which leaderboards to update based on:
        - evaluation_mode (single_turn vs multi_turn)
        - Metrics available in the run
        - Property types in the run
        
        Args:
            run_result: BenchmarkRunResult to add
            
        Returns:
            List of leaderboard IDs that were updated
        """
        updated = []
        mode = run_result.evaluation_mode
        
        # Get per-property scores for property-specific leaderboards
        property_scores = self._compute_property_scores(run_result)
        
        # Create the entry for overall leaderboards
        overall_entry = self._create_entry_from_run(
            run_result=run_result,
            score=run_result.overall_average_score,
            breakdown=self._get_score_breakdown(run_result),
        )
        
        # Add to overall leaderboard
        overall_lb_id = f"overall_{mode}"
        if self._add_entry(overall_lb_id, overall_entry):
            updated.append(overall_lb_id)
        
        # Add to per-metric leaderboards
        breakdown = self._get_score_breakdown(run_result)
        for metric in ["completeness", "robustness", "syntactic_validity"]:
            if metric in breakdown:
                metric_entry = self._create_entry_from_run(
                    run_result=run_result,
                    score=breakdown[metric],
                    breakdown=breakdown,
                )
                metric_lb_id = f"{metric}_{mode}"
                if self._add_entry(metric_lb_id, metric_entry):
                    updated.append(metric_lb_id)
        
        # Add to per-property leaderboards
        for prop_type, prop_score in property_scores.items():
            prop_entry = self._create_entry_from_run(
                run_result=run_result,
                score=prop_score,
                breakdown=breakdown,
            )
            prop_lb_id = f"{prop_type}_{mode}"
            if self._add_entry(prop_lb_id, prop_entry):
                updated.append(prop_lb_id)
        
        return updated

    def add_single_result(self, result: BenchmarkResult) -> List[str]:
        """
        Add a single BenchmarkResult to appropriate leaderboards.
        
        This is a convenience method for adding individual task results
        (e.g., from run-task command) rather than aggregated BenchmarkRunResult.
        
        Args:
            result: BenchmarkResult to add
            
        Returns:
            List of leaderboard IDs that were updated
        """
        updated = []
        mode = result.evaluation_mode or "single_turn"
        
        # Infer property type from task_id
        property_type = None
        for prop in ["reachability", "bgp_configuration", "ospf_configuration"]:
            if result.task_id.startswith(prop.replace("_configuration", "").replace("_", "")):
                property_type = prop
                break
        
        # Create breakdown from scoring
        breakdown = {
            "completeness": result.scoring.completeness,
            "robustness": result.scoring.robustness,
            "syntactic_validity": result.scoring.syntactic_validity,
        }
        
        # Create entry for this result
        entry = LeaderboardEntry(
            testee_id=result.testee_id,
            model_version=getattr(result, 'model_version', None),
            score=result.scoring.final_score,
            run_id=result.run_id,
            timestamp=result.timestamp,
            num_tasks=1,  # Single task
            breakdown=breakdown,
        )
        
        # Add to overall leaderboard
        overall_lb_id = f"overall_{mode}"
        if self._add_entry(overall_lb_id, entry):
            updated.append(overall_lb_id)
        
        # Add to per-metric leaderboards
        for metric in ["completeness", "robustness", "syntactic_validity"]:
            metric_entry = LeaderboardEntry(
                testee_id=result.testee_id,
                model_version=getattr(result, 'model_version', None),
                score=breakdown[metric],
                run_id=result.run_id,
                timestamp=result.timestamp,
                num_tasks=1,
                breakdown=breakdown,
            )
            metric_lb_id = f"{metric}_{mode}"
            if self._add_entry(metric_lb_id, metric_entry):
                updated.append(metric_lb_id)
        
        # Add to property-specific leaderboard if applicable
        if property_type:
            prop_lb_id = f"{property_type}_{mode}"
            if self._add_entry(prop_lb_id, entry):
                updated.append(prop_lb_id)
        
        return updated

    def _add_entry(self, leaderboard_id: str, entry: LeaderboardEntry) -> bool:
        """
        Add an entry to a leaderboard.
        
        If the testee already exists, keeps the most recent entry.
        
        Args:
            leaderboard_id: Target leaderboard ID
            entry: Entry to add
            
        Returns:
            True if entry was added, False if leaderboard not found
        """
        return self._collection.add_entry(leaderboard_id, entry, keep_newest=True)

    def _create_entry_from_run(
        self,
        run_result: BenchmarkRunResult,
        score: float,
        breakdown: dict[str, float],
    ) -> LeaderboardEntry:
        """
        Create a LeaderboardEntry from a BenchmarkRunResult.
        
        Args:
            run_result: Source run result
            score: Score for this entry
            breakdown: Metric breakdown
            
        Returns:
            LeaderboardEntry
        """
        return LeaderboardEntry(
            testee_id=run_result.testee_id,
            model_version=run_result.model_version,
            score=score,
            run_id=run_result.run_id,
            timestamp=run_result.timestamp,
            num_tasks=run_result.total_tasks,
            breakdown=breakdown,
        )

    def _get_score_breakdown(self, run_result: BenchmarkRunResult) -> dict[str, float]:
        """
        Compute aggregate score breakdown from a run result.
        
        Averages completeness, robustness, and syntactic_validity across
        all tasks in the run.
        
        Args:
            run_result: BenchmarkRunResult
            
        Returns:
            Dictionary of metric -> average score
        """
        metrics = {
            "completeness": [],
            "robustness": [],
            "syntactic_validity": [],
        }
        
        for prop_result in run_result.property_results.values():
            for task_result in prop_result.results:
                scoring = task_result.scoring
                metrics["completeness"].append(scoring.completeness)
                metrics["robustness"].append(scoring.robustness)
                metrics["syntactic_validity"].append(scoring.syntactic_validity)
        
        breakdown = {}
        for metric, values in metrics.items():
            if values:
                breakdown[metric] = sum(values) / len(values)
        
        return breakdown

    def _compute_property_scores(self, run_result: BenchmarkRunResult) -> dict[str, float]:
        """
        Compute per-property average scores from a run result.
        
        Args:
            run_result: BenchmarkRunResult
            
        Returns:
            Dictionary of property_type -> average score
        """
        scores = {}
        
        for prop_type, prop_result in run_result.property_results.items():
            if prop_result.results:
                scores[prop_type] = prop_result.average_score
        
        return scores

    def save_leaderboards(self, path: Optional[str] = None) -> str:
        """
        Save leaderboards to a JSON file.
        
        Args:
            path: Path to save to (uses constructor path if not provided)
            
        Returns:
            Absolute path to the saved file
            
        Raises:
            ValueError: If no path provided and no path set in constructor
        """
        save_path = Path(path) if path else self._path
        if not save_path:
            raise ValueError("No path provided for saving leaderboards")
        
        # Ensure parent directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Serialize and save
        with open(save_path, "w") as f:
            f.write(self._collection.model_dump_json(indent=2))
        
        return str(save_path.absolute())

    def load_leaderboards(self, path: Optional[str] = None) -> None:
        """
        Load leaderboards from a JSON file.
        
        Args:
            path: Path to load from (uses constructor path if not provided)
            
        Raises:
            ValueError: If no path provided and no path set in constructor
            FileNotFoundError: If file doesn't exist
        """
        load_path = Path(path) if path else self._path
        if not load_path:
            raise ValueError("No path provided for loading leaderboards")
        
        with open(load_path, "r") as f:
            data = f.read()
        
        self._collection = LeaderboardCollection.model_validate_json(data)
        
        # Update internal path if loading from new location
        if path:
            self._path = load_path
