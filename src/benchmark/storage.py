"""
Results Storage - Persistence layer for benchmark results.

This module handles saving, loading, and analyzing benchmark results
for research purposes. Results are stored as JSON files in a structured
directory hierarchy.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from benchmark.models.results import (
    BenchmarkResult,
    PropertyExecutionResult,
    BenchmarkRunResult,
)


class ResultsStorage:
    """
    Handles persistence and retrieval of benchmark results.
    
    Results are stored in a structured directory hierarchy:
    results/
    ├── runs/
    │   ├── {task_id}/
    │   │   ├── {run_id}.json
    │   │   └── {run_id}.json
    │   └── {task_id}/
    │       └── {run_id}.json
    └── analysis/
        ├── {study_id}.json
        └── {study_id}.json
    """

    def __init__(self, base_dir: str = "results/", experiment: str = ""):
        """
        Initialize ResultsStorage with base directory.

        Args:
            base_dir: Base directory for storing results (default: "results/")
            experiment: Optional subfolder inserted between "runs/" and the task
                directory (e.g. "reveal" → runs/reveal/{task_id}/). Leave empty
                to keep the flat runs/{task_id}/ layout.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._experiment = experiment

    def save_result(self, result: BenchmarkResult) -> str:
        """
        Save a single benchmark result to disk.
        
        Creates directory structure: results/runs/{task_id}/{run_id}.json
        
        Args:
            result: BenchmarkResult to save
            
        Returns:
            Absolute path to the saved file
        """
        return self.save_run(result)

    def save_run(self, result: BenchmarkResult) -> str:
        """
        Save a benchmark result to disk.

        Creates directory structure:
          - results/runs/{task_id}/{run_id}.json  (default)
          - results/runs/{experiment}/{task_id}/{run_id}.json  (when experiment set)

        Args:
            result: BenchmarkResult to save

        Returns:
            Absolute path to the saved file
        """
        # Create task directory
        runs_root = self.base_dir / "runs"
        if self._experiment:
            task_dir = runs_root / self._experiment / result.task_id
        else:
            task_dir = runs_root / result.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Create file path
        file_path = task_dir / f"{result.run_id}.json"
        
        # Convert to dict and save as JSON
        result_dict = result.model_dump()
        
        # Convert datetime to ISO string for JSON serialization
        if "timestamp" in result_dict:
            result_dict["timestamp"] = result_dict["timestamp"].isoformat()
        
        # Convert property results timestamps
        if "property_results" in result_dict:
            for prop_result in result_dict["property_results"]:
                if "timestamp" in prop_result:
                    prop_result["timestamp"] = prop_result["timestamp"].isoformat()
        
        # Convert execution log entries timestamps
        if "execution_log" in result_dict:
            # execution_log is a list of strings, not objects with timestamps
            pass
        
        with open(file_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        return str(file_path.absolute())

    def load_run(self, run_id: str) -> BenchmarkResult:
        """
        Load a benchmark result by run_id.
        
        Searches all task directories for the specified run_id.
        
        Args:
            run_id: Unique identifier for the run
            
        Returns:
            BenchmarkResult object
            
        Raises:
            FileNotFoundError: If run_id is not found
            Exception: If JSON parsing fails
        """
        runs_dir = self.base_dir / "runs"
        
        if not runs_dir.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")
        
        # Search all task directories
        for task_dir in runs_dir.iterdir():
            if not task_dir.is_dir():
                continue
                
            run_file = task_dir / f"{run_id}.json"
            if run_file.exists():
                try:
                    with open(run_file, 'r') as f:
                        data = json.load(f)
                    
                    # Convert ISO timestamp back to datetime
                    if "timestamp" in data:
                        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                    
                    # Convert property results timestamps
                    if "property_results" in data:
                        for prop_result in data["property_results"]:
                            if "timestamp" in prop_result:
                                prop_result["timestamp"] = datetime.fromisoformat(prop_result["timestamp"])
                    
                    return BenchmarkResult.model_validate(data)
                    
                except (json.JSONDecodeError, ValueError) as e:
                    raise Exception(f"Failed to parse result file {run_file}: {str(e)}")
        
        raise FileNotFoundError(f"Run not found: {run_id}")

    def list_runs(self, task_id: Optional[str] = None) -> List[str]:
        """
        List all run_ids, optionally filtered by task_id.
        
        Args:
            task_id: Optional task ID to filter by
            
        Returns:
            List of run_ids
        """
        runs_dir = self.base_dir / "runs"
        run_ids = []
        
        if not runs_dir.exists():
            return run_ids
        
        if task_id:
            # List runs for specific task
            task_dir = runs_dir / task_id
            if task_dir.exists() and task_dir.is_dir():
                for run_file in task_dir.glob("*.json"):
                    if run_file.is_file():
                        run_ids.append(run_file.stem)  # filename without extension
        else:
            # List all runs across all tasks
            for task_dir in runs_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                    
                for run_file in task_dir.glob("*.json"):
                    if run_file.is_file():
                        run_ids.append(run_file.stem)
        
        return sorted(run_ids)

    def compute_aggregate_stats(self, run_ids: List[str]) -> Dict[str, Any]:
        """
        Compute aggregate statistics for a list of runs.
        
        Args:
            run_ids: List of run_ids to analyze
            
        Returns:
            Dictionary with aggregate statistics and metadata
        """
        if not run_ids:
            return {
                "metadata": {
                    "total_runs": 0,
                    "run_ids": [],
                    "computed_date": datetime.now().isoformat(),
                },
                "aggregate_stats": {
                    "average_completeness": 0.0,
                    "average_robustness": 0.0,
                    "average_syntactic_validity": 0.0,
                    "average_efficiency": 0.0,
                    "average_final_score": 0.0,
                    "valid_solution_rate": 0.0,
                    "average_infrastructure_provision_time": 0.0,
                    "average_config_execution_time": 0.0,
                    "average_convergence_time": 0.0,
                    "average_evaluation_time": 0.0,
                    "average_total_time": 0.0,
                },
                "grouped_by_testee_type": {},
                "grouped_by_testee_id": {},
                "grouped_by_task_id": {},
            }
        
        # Load all results
        results = []
        for run_id in run_ids:
            try:
                result = self.load_run(run_id)
                results.append(result)
            except (FileNotFoundError, Exception):
                # Skip invalid runs
                continue
        
        if not results:
            return self.compute_aggregate_stats([])  # Return empty stats
        
        # Compute aggregate statistics
        total_runs = len(results)
        
        # Average scores
        avg_completeness = sum(r.scoring.completeness for r in results) / total_runs
        avg_robustness = sum(r.scoring.robustness for r in results) / total_runs
        avg_syntactic_validity = sum(r.scoring.syntactic_validity for r in results) / total_runs
        
        # Handle efficiency (some may be None)
        efficiency_values = [r.scoring.efficiency for r in results if r.scoring.efficiency is not None]
        avg_efficiency = sum(efficiency_values) / len(efficiency_values) if efficiency_values else 0.0
        
        avg_final_score = sum(r.scoring.final_score for r in results) / total_runs
        
        # Valid solution rate
        valid_solutions = sum(1 for r in results if r.validity.is_valid_solution)
        valid_solution_rate = valid_solutions / total_runs
        
        # Average execution times
        avg_provision_time = sum(r.metrics.infrastructure_provision_time for r in results) / total_runs
        avg_config_time = sum(r.metrics.config_execution_time for r in results) / total_runs
        avg_convergence_time = sum(r.metrics.convergence_time for r in results) / total_runs
        avg_evaluation_time = sum(r.metrics.evaluation_time for r in results) / total_runs
        avg_total_time = sum(r.metrics.total_time for r in results) / total_runs
        
        # Group by testee_type
        grouped_by_testee_type = {}
        for result in results:
            testee_type = result.testee_type
            if testee_type not in grouped_by_testee_type:
                grouped_by_testee_type[testee_type] = []
            grouped_by_testee_type[testee_type].append(result.run_id)
        
        # Group by testee_id
        grouped_by_testee_id = {}
        for result in results:
            testee_id = result.testee_id
            if testee_id not in grouped_by_testee_id:
                grouped_by_testee_id[testee_id] = []
            grouped_by_testee_id[testee_id].append(result.run_id)
        
        # Group by task_id
        grouped_by_task_id = {}
        for result in results:
            task_id = result.task_id
            if task_id not in grouped_by_task_id:
                grouped_by_task_id[task_id] = []
            grouped_by_task_id[task_id].append(result.run_id)
        
        return {
            "metadata": {
                "total_runs": total_runs,
                "run_ids": [r.run_id for r in results],
                "computed_date": datetime.now().isoformat(),
            },
            "aggregate_stats": {
                "average_completeness": avg_completeness,
                "average_robustness": avg_robustness,
                "average_syntactic_validity": avg_syntactic_validity,
                "average_efficiency": avg_efficiency,
                "average_final_score": avg_final_score,
                "valid_solution_rate": valid_solution_rate,
                "average_infrastructure_provision_time": avg_provision_time,
                "average_config_execution_time": avg_config_time,
                "average_convergence_time": avg_convergence_time,
                "average_evaluation_time": avg_evaluation_time,
                "average_total_time": avg_total_time,
            },
            "grouped_by_testee_type": grouped_by_testee_type,
            "grouped_by_testee_id": grouped_by_testee_id,
            "grouped_by_task_id": grouped_by_task_id,
        }

    def save_aggregate_stats(self, study_id: str, stats: Dict[str, Any]) -> str:
        """
        Save aggregate statistics to disk.
        
        Args:
            study_id: Unique identifier for the study
            stats: Statistics dictionary to save
            
        Returns:
            Absolute path to the saved file
        """
        # Create analysis directory
        analysis_dir = self.base_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        
        # Create file path
        file_path = analysis_dir / f"{study_id}.json"
        
        # Save as JSON (don't modify the input stats)
        with open(file_path, 'w') as f:
            json.dump(stats, f, indent=2)
        
        return str(file_path.absolute())

    def save_property_result(self, result: PropertyExecutionResult) -> str:
        """
        Save a property execution result to disk.
        
        Args:
            result: PropertyExecutionResult to save
            
        Returns:
            Absolute path to the saved file
        """
        # Create property results directory
        property_dir = self.base_dir / "property_results"
        property_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate a unique ID for this property result
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_result_id = f"{result.property_type}_{timestamp}"
        file_path = property_dir / f"{property_result_id}.json"
        
        # Convert to dict and save as JSON
        result_dict = result.model_dump()
        
        # Convert datetime timestamps in nested results
        if "results" in result_dict:
            for benchmark_result in result_dict["results"]:
                if "timestamp" in benchmark_result:
                    benchmark_result["timestamp"] = benchmark_result["timestamp"].isoformat()
                if "property_results" in benchmark_result:
                    for prop_result in benchmark_result["property_results"]:
                        if "timestamp" in prop_result:
                            prop_result["timestamp"] = prop_result["timestamp"].isoformat()
        
        with open(file_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        return str(file_path.absolute())

    def save_benchmark_run(self, result: BenchmarkRunResult) -> str:
        """
        Save a complete benchmark run result to disk.
        
        Args:
            result: BenchmarkRunResult to save
            
        Returns:
            Absolute path to the saved file
        """
        # Create benchmark runs directory
        runs_dir = self.base_dir / "benchmark_runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create file path using run_id
        file_path = runs_dir / f"{result.run_id}.json"
        
        # Convert to dict and save as JSON
        result_dict = result.model_dump()
        
        # Convert timestamp
        if "timestamp" in result_dict:
            result_dict["timestamp"] = result_dict["timestamp"].isoformat()
        
        # Convert timestamps in property results
        if "property_results" in result_dict:
            for prop_type, prop_result in result_dict["property_results"].items():
                if "results" in prop_result:
                    for benchmark_result in prop_result["results"]:
                        if "timestamp" in benchmark_result:
                            benchmark_result["timestamp"] = benchmark_result["timestamp"].isoformat()
                        if "property_results" in benchmark_result:
                            for pr in benchmark_result["property_results"]:
                                if "timestamp" in pr:
                                    pr["timestamp"] = pr["timestamp"].isoformat()
        
        with open(file_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        return str(file_path.absolute())

    def list_recent_runs(
        self, limit: int = 10, task_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List recent benchmark runs with metadata.
        
        Args:
            limit: Number of recent runs to return
            task_id: Optional task ID to filter by
            
        Returns:
            List of run metadata dictionaries
        """
        runs_dir = self.base_dir / "runs"
        run_info_list = []
        
        if not runs_dir.exists():
            return run_info_list
        
        # Collect all run files with metadata
        for task_dir in runs_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            # Skip if filtering by task_id and this isn't the target
            if task_id and task_dir.name != task_id:
                continue
            
            for run_file in task_dir.glob("*.json"):
                if not run_file.is_file():
                    continue
                
                try:
                    with open(run_file, 'r') as f:
                        data = json.load(f)
                    
                    run_info_list.append({
                        "run_id": data.get("run_id", run_file.stem),
                        "task_id": data.get("task_id", task_dir.name),
                        "score": data.get("scoring", {}).get("final_score", 0.0),
                        "timestamp": data.get("timestamp", "unknown"),
                        "testee_id": data.get("testee_id", "unknown"),
                    })
                except (json.JSONDecodeError, Exception):
                    # Skip invalid files
                    continue
        
        # Sort by timestamp (newest first) and limit
        run_info_list.sort(
            key=lambda x: x["timestamp"], reverse=True
        )
        
        return run_info_list[:limit]

    def load_result(self, run_id: str) -> BenchmarkResult:
        """
        Load a benchmark result by run_id (alias for load_run).
        
        Args:
            run_id: Unique identifier for the run
            
        Returns:
            BenchmarkResult object
        """
        return self.load_run(run_id)

    def get_runs_by_testee(self, testee_id: str) -> List[BenchmarkResult]:
        """
        Load all runs for a specific testee.
        
        Args:
            testee_id: Testee identifier to filter by
            
        Returns:
            List of BenchmarkResult objects for this testee
        """
        runs_dir = self.base_dir / "runs"
        results = []
        
        if not runs_dir.exists():
            return results
        
        # Search all task directories
        for task_dir in runs_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            for run_file in task_dir.glob("*.json"):
                if not run_file.is_file():
                    continue
                
                try:
                    with open(run_file, 'r') as f:
                        data = json.load(f)
                    
                    # Check if this run is for the target testee
                    if data.get("testee_id") == testee_id:
                        # Convert ISO timestamp back to datetime
                        if "timestamp" in data:
                            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                        
                        # Convert property results timestamps
                        if "property_results" in data:
                            for prop_result in data["property_results"]:
                                if "timestamp" in prop_result:
                                    prop_result["timestamp"] = datetime.fromisoformat(prop_result["timestamp"])
                        
                        result = BenchmarkResult.model_validate(data)
                        results.append(result)
                except (json.JSONDecodeError, ValueError, Exception):
                    # Skip invalid files
                    continue
        
        return results

    def get_runs_by_property(self, property_type: str) -> List[BenchmarkResult]:
        """
        Load all runs for a specific property type.
        
        Infers property type from task_id (e.g., task_id starting with "reachability_").
        
        Args:
            property_type: Property type identifier (e.g., "reachability", "bgp_configuration")
            
        Returns:
            List of BenchmarkResult objects for this property type
        """
        runs_dir = self.base_dir / "runs"
        results = []
        
        if not runs_dir.exists():
            return results
        
        # Search all task directories
        for task_dir in runs_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            # Check if task_dir name starts with property_type prefix
            # e.g., "reachability_", "bgp_", "ospf_"
            task_dir_name = task_dir.name
            property_prefix = property_type.replace("_configuration", "").replace("_", "")
            
            if not task_dir_name.startswith(property_prefix):
                continue
            
            for run_file in task_dir.glob("*.json"):
                if not run_file.is_file():
                    continue
                
                try:
                    with open(run_file, 'r') as f:
                        data = json.load(f)
                    
                    # Convert ISO timestamp back to datetime
                    if "timestamp" in data:
                        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                    
                    # Convert property results timestamps
                    if "property_results" in data:
                        for prop_result in data["property_results"]:
                            if "timestamp" in prop_result:
                                prop_result["timestamp"] = datetime.fromisoformat(prop_result["timestamp"])
                    
                    result = BenchmarkResult.model_validate(data)
                    results.append(result)
                except (json.JSONDecodeError, ValueError, Exception):
                    # Skip invalid files
                    continue
        
        return results

    def get_matched_runs(
        self, testee_ids: List[str]
    ) -> Dict[str, Dict[str, BenchmarkResult]]:
        """
        Load runs for comparison, matched by task_id.
        
        Only includes tasks that have results from ALL specified testees.
        
        Args:
            testee_ids: List of testee IDs to match
            
        Returns:
            Dictionary mapping task_id to dict of {testee_id: BenchmarkResult}
            Only tasks present for ALL testees are included.
        """
        # First, get all runs for each testee
        testee_runs = {}
        for testee_id in testee_ids:
            testee_runs[testee_id] = self.get_runs_by_testee(testee_id)
        
        # Group by task_id
        task_groups: Dict[str, Dict[str, BenchmarkResult]] = {}
        
        for testee_id, runs in testee_runs.items():
            for run in runs:
                task_id = run.task_id
                if task_id not in task_groups:
                    task_groups[task_id] = {}
                task_groups[task_id][testee_id] = run
        
        # Filter to only include tasks with all testees
        matched_runs = {}
        for task_id, testee_dict in task_groups.items():
            if all(testee_id in testee_dict for testee_id in testee_ids):
                matched_runs[task_id] = testee_dict
        
        return matched_runs

    # =========================================================================
    # Leaderboard Persistence
    # =========================================================================

    @property
    def leaderboards_path(self) -> Path:
        """
        Get the path to the leaderboards JSON file.
        
        Returns:
            Path to leaderboards.json in base_dir
        """
        return self.base_dir / "leaderboards.json"

    def save_leaderboards(self, collection: "LeaderboardCollection") -> str:
        """
        Save a LeaderboardCollection to disk.
        
        Args:
            collection: LeaderboardCollection to save
            
        Returns:
            Absolute path to the saved file
        """
        from benchmark.models.leaderboard import LeaderboardCollection
        
        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Save collection as JSON
        with open(self.leaderboards_path, "w") as f:
            f.write(collection.model_dump_json(indent=2))
        
        return str(self.leaderboards_path.absolute())

    def load_leaderboards(self) -> Optional["LeaderboardCollection"]:
        """
        Load a LeaderboardCollection from disk.
        
        Returns:
            LeaderboardCollection if file exists, None otherwise
        """
        from benchmark.models.leaderboard import LeaderboardCollection
        
        if not self.leaderboards_path.exists():
            return None
        
        with open(self.leaderboards_path, "r") as f:
            data = f.read()
        
        return LeaderboardCollection.model_validate_json(data)

    def get_leaderboard_manager(self) -> "LeaderboardManager":
        """
        Get a LeaderboardManager configured with this storage.
        
        If leaderboards exist, loads them. Otherwise, returns an
        empty manager ready for initialization.
        
        Returns:
            LeaderboardManager instance
        """
        from benchmark.analysis.leaderboard import LeaderboardManager
        
        manager = LeaderboardManager(leaderboards_path=str(self.leaderboards_path))
        return manager

    def load_benchmark_run(self, run_id: str) -> Optional[BenchmarkRunResult]:
        """
        Load a BenchmarkRunResult by run_id.
        
        Args:
            run_id: Unique identifier for the benchmark run
            
        Returns:
            BenchmarkRunResult if found, None otherwise
        """
        runs_dir = self.base_dir / "benchmark_runs"
        
        if not runs_dir.exists():
            return None
        
        run_file = runs_dir / f"{run_id}.json"
        if not run_file.exists():
            return None
        
        try:
            with open(run_file, "r") as f:
                data = json.load(f)
            
            # Convert ISO timestamp back to datetime
            if "timestamp" in data:
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            
            # Convert timestamps in property results
            if "property_results" in data:
                for prop_type, prop_result in data["property_results"].items():
                    if "results" in prop_result:
                        for benchmark_result in prop_result["results"]:
                            if "timestamp" in benchmark_result:
                                benchmark_result["timestamp"] = datetime.fromisoformat(
                                    benchmark_result["timestamp"]
                                )
                            if "property_results" in benchmark_result:
                                for pr in benchmark_result["property_results"]:
                                    if "timestamp" in pr:
                                        pr["timestamp"] = datetime.fromisoformat(
                                            pr["timestamp"]
                                        )
            
            return BenchmarkRunResult.model_validate(data)
        except (json.JSONDecodeError, ValueError, Exception):
            return None

    def list_benchmark_runs(self) -> List[str]:
        """
        List all BenchmarkRunResult run_ids.
        
        Returns:
            List of run_ids
        """
        runs_dir = self.base_dir / "benchmark_runs"
        
        if not runs_dir.exists():
            return []
        
        run_ids = []
        for run_file in runs_dir.glob("*.json"):
            if run_file.is_file():
                run_ids.append(run_file.stem)
        
        return sorted(run_ids)

