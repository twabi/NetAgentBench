"""
Unit tests for ResultsStorage.

Tests the results persistence and retrieval functionality.
"""

import json
import os
import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from benchmark.storage import ResultsStorage
from benchmark.models.task import (
    TaskDefinition,
    TopologySpecification,
    Node,
    NodeType,
    Platform,
    IntentSpecification,
    Property,
    PropertyType,
    EvaluationProcedure,
    ConvergenceConfig,
    OptimalSolution,
)
from benchmark.models.submission import (
    Submission,
    Approach,
    CommandSequence,
)
from benchmark.models.results import (
    BenchmarkResult,
    PropertyEvaluationResult,
    ScoringResult,
    ValidityCheck,
    ExecutionMetrics,
)
from benchmark.executor.command import ExecutionLogEntry


class TestResultsStorageInitialization:
    """Test ResultsStorage initialization"""

    def test_storage_initializes_with_default_base_dir(self):
        """Test that storage initializes with default base directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            assert storage.base_dir == Path(temp_dir)
            assert storage.base_dir.exists()

    def test_storage_initializes_with_custom_base_dir(self):
        """Test that storage initializes with custom base directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_dir = Path(temp_dir) / "custom_results"
            storage = ResultsStorage(base_dir=str(custom_dir))
            assert storage.base_dir == custom_dir
            assert storage.base_dir.exists()

    def test_storage_creates_base_directory_if_not_exists(self):
        """Test that storage creates base directory if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_dir = Path(temp_dir) / "new_results"
            assert not non_existent_dir.exists()
            
            storage = ResultsStorage(base_dir=str(non_existent_dir))
            assert storage.base_dir.exists()
            assert storage.base_dir == non_existent_dir


class TestResultsStorageSaveRun:
    """Test save_run method"""

    @pytest.fixture
    def sample_result(self):
        """Create a sample BenchmarkResult for testing"""
        return BenchmarkResult(
            run_id="test_run_001",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            task_id="test_task_001",
            testee_id="test_testee",
            testee_type="test",
            success=True,
            property_results=[
                PropertyEvaluationResult(
                    property_id="prop1",
                    satisfied=True,
                    observation_raw="test output",
                    observation_parsed={"found": True},
                    evaluation_time_seconds=0.1,
                    error_message=None,
                )
            ],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                efficiency=1.0,
                final_score=1.0,
                weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=3.0,
                evaluation_time=4.0,
                total_time=10.0,
            ),
            execution_log=["2024-01-01T12:00:00 | node1 | command1 | ✓"],
            errors=[],
        )

    def test_save_run_creates_correct_directory_structure(self, sample_result):
        """Test that save_run creates the correct directory structure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            file_path = storage.save_run(sample_result)
            
            # Verify directory structure
            expected_dir = Path(temp_dir) / "runs" / "test_task_001"
            assert expected_dir.exists()
            assert expected_dir.is_dir()
            
            # Verify file path
            expected_file = expected_dir / "test_run_001.json"
            assert file_path == str(expected_file)
            assert Path(file_path).exists()

    def test_save_run_creates_valid_json_file(self, sample_result):
        """Test that save_run creates a valid JSON file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            file_path = storage.save_run(sample_result)
            
            # Verify file exists and is valid JSON
            assert Path(file_path).exists()
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Verify key fields
            assert data["run_id"] == "test_run_001"
            assert data["task_id"] == "test_task_001"
            assert data["testee_id"] == "test_testee"
            assert data["success"] is True
            assert data["scoring"]["final_score"] == 1.0

    def test_save_run_handles_multiple_runs_same_task(self, sample_result):
        """Test that save_run handles multiple runs for the same task"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save first run
            result1 = sample_result
            file_path1 = storage.save_run(result1)
            
            # Save second run with different run_id
            result2 = sample_result.model_copy(update={"run_id": "test_run_002"})
            file_path2 = storage.save_run(result2)
            
            # Both files should exist
            assert Path(file_path1).exists()
            assert Path(file_path2).exists()
            assert file_path1 != file_path2
            
            # Both should be in the same task directory
            assert "test_task_001" in file_path1
            assert "test_task_001" in file_path2

    def test_save_run_handles_multiple_tasks(self, sample_result):
        """Test that save_run handles multiple different tasks"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save run for task 1
            result1 = sample_result
            file_path1 = storage.save_run(result1)
            
            # Save run for task 2
            result2 = sample_result.model_copy(update={"task_id": "test_task_002"})
            file_path2 = storage.save_run(result2)
            
            # Both files should exist
            assert Path(file_path1).exists()
            assert Path(file_path2).exists()
            
            # Should be in different task directories
            assert "test_task_001" in file_path1
            assert "test_task_002" in file_path2

    def test_save_run_returns_correct_file_path(self, sample_result):
        """Test that save_run returns the correct file path"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            file_path = storage.save_run(sample_result)
            
            # Should be absolute path
            assert Path(file_path).is_absolute()
            
            # Should match expected pattern
            expected_pattern = f"{temp_dir}/runs/test_task_001/test_run_001.json"
            assert file_path == expected_pattern


class TestResultsStorageLoadRun:
    """Test load_run method"""

    @pytest.fixture
    def sample_result(self):
        """Create a sample BenchmarkResult for testing"""
        return BenchmarkResult(
            run_id="test_run_001",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            task_id="test_task_001",
            testee_id="test_testee",
            testee_type="test",
            success=True,
            property_results=[
                PropertyEvaluationResult(
                    property_id="prop1",
                    satisfied=True,
                    observation_raw="test output",
                    observation_parsed={"found": True},
                    evaluation_time_seconds=0.1,
                    error_message=None,
                )
            ],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                efficiency=1.0,
                final_score=1.0,
                weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=3.0,
                evaluation_time=4.0,
                total_time=10.0,
            ),
            execution_log=["2024-01-01T12:00:00 | node1 | command1 | ✓"],
            errors=[],
        )

    def test_load_run_retrieves_correct_result(self, sample_result):
        """Test that load_run retrieves the correct result"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save a result
            file_path = storage.save_run(sample_result)
            
            # Load it back
            loaded_result = storage.load_run("test_run_001")
            
            # Should match original
            assert loaded_result.run_id == sample_result.run_id
            assert loaded_result.task_id == sample_result.task_id
            assert loaded_result.testee_id == sample_result.testee_id
            assert loaded_result.success == sample_result.success
            assert loaded_result.scoring.final_score == sample_result.scoring.final_score

    def test_load_run_searches_all_task_directories(self, sample_result):
        """Test that load_run searches all task directories for the run_id"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save runs in different task directories
            result1 = sample_result
            storage.save_run(result1)
            
            result2 = sample_result.model_copy(update={
                "run_id": "test_run_002",
                "task_id": "test_task_002"
            })
            storage.save_run(result2)
            
            # Should find both runs regardless of task
            loaded1 = storage.load_run("test_run_001")
            loaded2 = storage.load_run("test_run_002")
            
            assert loaded1.run_id == "test_run_001"
            assert loaded2.run_id == "test_run_002"

    def test_load_run_raises_exception_for_nonexistent_run(self):
        """Test that load_run raises exception for nonexistent run_id"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            with pytest.raises(FileNotFoundError, match="Run not found"):
                storage.load_run("nonexistent_run")

    def test_load_run_handles_corrupted_json_file(self, sample_result):
        """Test that load_run handles corrupted JSON files gracefully"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save a result
            file_path = storage.save_run(sample_result)
            
            # Corrupt the file
            with open(file_path, 'w') as f:
                f.write("invalid json content")
            
            # Should raise exception
            with pytest.raises(Exception, match="Failed to parse"):
                storage.load_run("test_run_001")


class TestResultsStorageListRuns:
    """Test list_runs method"""

    @pytest.fixture
    def sample_result(self):
        """Create a sample BenchmarkResult for testing"""
        return BenchmarkResult(
            run_id="test_run_001",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            task_id="test_task_001",
            testee_id="test_testee",
            testee_type="test",
            success=True,
            property_results=[],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                efficiency=1.0,
                final_score=1.0,
                weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=3.0,
                evaluation_time=4.0,
                total_time=10.0,
            ),
            execution_log=[],
            errors=[],
        )

    def test_list_runs_returns_all_runs_when_no_task_filter(self, sample_result):
        """Test that list_runs returns all runs when no task filter is provided"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save runs for different tasks
            result1 = sample_result
            storage.save_run(result1)
            
            result2 = sample_result.model_copy(update={
                "run_id": "test_run_002",
                "task_id": "test_task_002"
            })
            storage.save_run(result2)
            
            result3 = sample_result.model_copy(update={
                "run_id": "test_run_003",
                "task_id": "test_task_001"
            })
            storage.save_run(result3)
            
            # List all runs
            runs = storage.list_runs()
            
            # Should return all 3 runs
            assert len(runs) == 3
            assert "test_run_001" in runs
            assert "test_run_002" in runs
            assert "test_run_003" in runs

    def test_list_runs_filters_by_task_id(self, sample_result):
        """Test that list_runs filters by task_id when provided"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save runs for different tasks
            result1 = sample_result
            storage.save_run(result1)
            
            result2 = sample_result.model_copy(update={
                "run_id": "test_run_002",
                "task_id": "test_task_002"
            })
            storage.save_run(result2)
            
            result3 = sample_result.model_copy(update={
                "run_id": "test_run_003",
                "task_id": "test_task_001"
            })
            storage.save_run(result3)
            
            # List runs for specific task
            runs = storage.list_runs(task_id="test_task_001")
            
            # Should return only runs for test_task_001
            assert len(runs) == 2
            assert "test_run_001" in runs
            assert "test_run_003" in runs
            assert "test_run_002" not in runs

    def test_list_runs_returns_empty_list_when_no_runs(self):
        """Test that list_runs returns empty list when no runs exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            runs = storage.list_runs()
            assert runs == []

    def test_list_runs_returns_empty_list_for_nonexistent_task(self, sample_result):
        """Test that list_runs returns empty list for nonexistent task"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save a run
            storage.save_run(sample_result)
            
            # List runs for nonexistent task
            runs = storage.list_runs(task_id="nonexistent_task")
            assert runs == []


class TestResultsStorageComputeAggregateStats:
    """Test compute_aggregate_stats method"""

    @pytest.fixture
    def sample_results(self):
        """Create sample BenchmarkResults for testing"""
        base_result = BenchmarkResult(
            run_id="test_run_001",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            task_id="test_task_001",
            testee_id="test_testee",
            testee_type="test",
            success=True,
            property_results=[],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                efficiency=1.0,
                final_score=1.0,
                weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=3.0,
                evaluation_time=4.0,
                total_time=10.0,
            ),
            execution_log=[],
            errors=[],
        )
        
        return [
            base_result,
            base_result.model_copy(update={
                "run_id": "test_run_002",
                "scoring": ScoringResult(
                    completeness=0.8,
                    robustness=0.8,
                    syntactic_validity=0.8,
                    efficiency=0.8,
                    final_score=0.8,
                    weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
                ),
                "validity": ValidityCheck(
                    is_valid_solution=False,
                    condition_a_syntactic=True,
                    condition_b_semantic=False,
                ),
            }),
            base_result.model_copy(update={
                "run_id": "test_run_003",
                "testee_id": "test_testee_2",
                "scoring": ScoringResult(
                    completeness=0.6,
                    robustness=0.6,
                    syntactic_validity=0.6,
                    efficiency=0.6,
                    final_score=0.6,
                    weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
                ),
            }),
        ]

    def test_compute_aggregate_stats_calculates_correct_averages(self, sample_results):
        """Test that compute_aggregate_stats calculates correct averages"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save all results
            run_ids = []
            for result in sample_results:
                storage.save_run(result)
                run_ids.append(result.run_id)
            
            # Compute aggregate stats
            stats = storage.compute_aggregate_stats(run_ids)
            
            # Verify structure
            assert "aggregate_stats" in stats
            assert "metadata" in stats
            
            # Verify metadata
            assert stats["metadata"]["total_runs"] == 3
            assert stats["metadata"]["run_ids"] == run_ids
            
            # Verify aggregate calculations
            agg = stats["aggregate_stats"]
            
            # Average completeness: (1.0 + 0.8 + 0.6) / 3 = 0.8
            assert abs(agg["average_completeness"] - 0.8) < 0.001
            assert abs(agg["average_robustness"] - 0.8) < 0.001
            assert abs(agg["average_syntactic_validity"] - 0.8) < 0.001
            assert abs(agg["average_efficiency"] - 0.8) < 0.001
            assert abs(agg["average_final_score"] - 0.8) < 0.001
            
            # Valid solution rate: 2 out of 3 = 0.666...
            assert abs(agg["valid_solution_rate"] - 2/3) < 0.001

    def test_compute_aggregate_stats_groups_by_testee_type(self, sample_results):
        """Test that compute_aggregate_stats groups by testee_type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save all results
            run_ids = []
            for result in sample_results:
                storage.save_run(result)
                run_ids.append(result.run_id)
            
            # Compute aggregate stats
            stats = storage.compute_aggregate_stats(run_ids)
            
            # Should have grouping by testee_type
            assert "grouped_by_testee_type" in stats
            grouped = stats["grouped_by_testee_type"]
            
            # All results have testee_type="test"
            assert "test" in grouped
            assert len(grouped["test"]) == 3

    def test_compute_aggregate_stats_groups_by_testee_id(self, sample_results):
        """Test that compute_aggregate_stats groups by testee_id"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save all results
            run_ids = []
            for result in sample_results:
                storage.save_run(result)
                run_ids.append(result.run_id)
            
            # Compute aggregate stats
            stats = storage.compute_aggregate_stats(run_ids)
            
            # Should have grouping by testee_id
            assert "grouped_by_testee_id" in stats
            grouped = stats["grouped_by_testee_id"]
            
            # Should have 2 different testee_ids
            assert "test_testee" in grouped
            assert "test_testee_2" in grouped
            assert len(grouped["test_testee"]) == 2
            assert len(grouped["test_testee_2"]) == 1

    def test_compute_aggregate_stats_handles_empty_run_list(self):
        """Test that compute_aggregate_stats handles empty run list"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            stats = storage.compute_aggregate_stats([])
            
            # Should return empty stats
            assert stats["metadata"]["total_runs"] == 0
            assert stats["aggregate_stats"]["average_final_score"] == 0.0

    def test_compute_aggregate_stats_handles_nonexistent_runs(self):
        """Test that compute_aggregate_stats handles nonexistent run_ids"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Should not crash
            stats = storage.compute_aggregate_stats(["nonexistent_run"])
            
            # Should return empty stats
            assert stats["metadata"]["total_runs"] == 0


class TestResultsStorageSaveAggregateStats:
    """Test save_aggregate_stats method"""

    def test_save_aggregate_stats_creates_correct_file(self):
        """Test that save_aggregate_stats creates the correct file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create sample stats
            stats = {
                "metadata": {
                    "study_id": "test_study",
                    "created_date": "2024-01-01",
                    "run_ids": ["run1", "run2"],
                    "total_runs": 2,
                },
                "aggregate_stats": {
                    "average_final_score": 0.8,
                    "valid_solution_rate": 0.5,
                },
            }
            
            # Save stats
            file_path = storage.save_aggregate_stats("test_study", stats)
            
            # Verify file exists
            expected_path = Path(temp_dir) / "analysis" / "test_study.json"
            assert file_path == str(expected_path)
            assert Path(file_path).exists()
            
            # Verify content
            with open(file_path, 'r') as f:
                loaded_stats = json.load(f)
            
            assert loaded_stats == stats

    def test_save_aggregate_stats_creates_analysis_directory(self):
        """Test that save_aggregate_stats creates analysis directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Verify analysis directory doesn't exist initially
            analysis_dir = Path(temp_dir) / "analysis"
            assert not analysis_dir.exists()
            
            # Save stats
            stats = {"metadata": {"study_id": "test"}, "aggregate_stats": {}}
            storage.save_aggregate_stats("test_study", stats)
            
            # Verify analysis directory was created
            assert analysis_dir.exists()
            assert analysis_dir.is_dir()

    def test_save_aggregate_stats_handles_multiple_studies(self):
        """Test that save_aggregate_stats handles multiple studies"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Save stats for different studies
            stats1 = {"metadata": {"study_id": "study1"}, "aggregate_stats": {}}
            file_path1 = storage.save_aggregate_stats("study1", stats1)
            
            stats2 = {"metadata": {"study_id": "study2"}, "aggregate_stats": {}}
            file_path2 = storage.save_aggregate_stats("study2", stats2)
            
            # Both files should exist
            assert Path(file_path1).exists()
            assert Path(file_path2).exists()
            assert file_path1 != file_path2
            
            # Should be in analysis directory
            assert "analysis" in file_path1
            assert "analysis" in file_path2


class TestResultsStorageQueryMethods:
    """Test query methods for analysis"""

    def test_get_runs_by_testee(self):
        """Test loading all runs for a specific testee"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create sample results for different testees
            result1 = BenchmarkResult(
                run_id="run1",
                timestamp=datetime.now(),
                task_id="task1",
                testee_id="gpt-4",
                testee_type="llm",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.8,
                    robustness=0.7,
                    syntactic_validity=0.9,
                    efficiency=None,
                    final_score=0.8,
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
            
            result2 = BenchmarkResult(
                run_id="run2",
                timestamp=datetime.now(),
                task_id="task2",
                testee_id="gpt-4",
                testee_type="llm",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.9,
                    robustness=0.8,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=0.9,
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
            
            result3 = BenchmarkResult(
                run_id="run3",
                timestamp=datetime.now(),
                task_id="task1",
                testee_id="baseline",
                testee_type="baseline",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.5,
                    robustness=0.5,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=0.6,
                    weights={},
                ),
                validity=ValidityCheck(
                    is_valid_solution=False,
                    condition_a_syntactic=True,
                    condition_b_semantic=False,
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
            
            # Save results
            storage.save_result(result1)
            storage.save_result(result2)
            storage.save_result(result3)
            
            # Query by testee
            gpt4_runs = storage.get_runs_by_testee("gpt-4")
            assert len(gpt4_runs) == 2
            assert all(r.testee_id == "gpt-4" for r in gpt4_runs)
            
            baseline_runs = storage.get_runs_by_testee("baseline")
            assert len(baseline_runs) == 1
            assert baseline_runs[0].testee_id == "baseline"
            
            # Non-existent testee
            empty_runs = storage.get_runs_by_testee("non-existent")
            assert len(empty_runs) == 0

    def test_get_runs_by_property(self):
        """Test loading all runs for a specific property type"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create results with different property types (inferred from task_id)
            prop1 = PropertyEvaluationResult(
                property_id="reach1",
                satisfied=True,
                observation_raw="output",
                observation_parsed=None,
                evaluation_time_seconds=2.0,
                error_message=None,
            )
            
            result1 = BenchmarkResult(
                run_id="run1",
                timestamp=datetime.now(),
                task_id="reachability_linear_2n",  # Property type inferred from task_id prefix
                testee_id="gpt-4",
                testee_type="llm",
                success=True,
                property_results=[prop1],
                scoring=ScoringResult(
                    completeness=0.8,
                    robustness=0.7,
                    syntactic_validity=0.9,
                    efficiency=None,
                    final_score=0.8,
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
            
            prop2 = PropertyEvaluationResult(
                property_id="bgp1",
                satisfied=True,
                observation_raw="output",
                observation_parsed=None,
                evaluation_time_seconds=2.0,
                error_message=None,
            )
            
            result2 = BenchmarkResult(
                run_id="run2",
                timestamp=datetime.now(),
                task_id="bgp_2as_basic",  # Property type inferred from task_id prefix
                testee_id="gpt-4",
                testee_type="llm",
                success=True,
                property_results=[prop2],
                scoring=ScoringResult(
                    completeness=0.9,
                    robustness=0.8,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=0.9,
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
            
            # Save results
            storage.save_result(result1)
            storage.save_result(result2)
            
            # Query by property type (inferred from task_id)
            reachability_runs = storage.get_runs_by_property("reachability")
            assert len(reachability_runs) == 1
            assert "reachability" in reachability_runs[0].task_id
            
            bgp_runs = storage.get_runs_by_property("bgp_configuration")
            assert len(bgp_runs) == 1
            assert "bgp" in bgp_runs[0].task_id

    def test_get_matched_runs(self):
        """Test loading matched runs for comparison"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create results for same tasks but different testees
            result1 = BenchmarkResult(
                run_id="run1",
                timestamp=datetime.now(),
                task_id="task1",
                testee_id="gpt-4",
                testee_type="llm",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.8,
                    robustness=0.7,
                    syntactic_validity=0.9,
                    efficiency=None,
                    final_score=0.8,
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
            
            result2 = BenchmarkResult(
                run_id="run2",
                timestamp=datetime.now(),
                task_id="task1",
                testee_id="baseline",
                testee_type="baseline",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.5,
                    robustness=0.5,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=0.6,
                    weights={},
                ),
                validity=ValidityCheck(
                    is_valid_solution=False,
                    condition_a_syntactic=True,
                    condition_b_semantic=False,
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
            
            result3 = BenchmarkResult(
                run_id="run3",
                timestamp=datetime.now(),
                task_id="task2",
                testee_id="gpt-4",
                testee_type="llm",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.9,
                    robustness=0.8,
                    syntactic_validity=1.0,
                    efficiency=None,
                    final_score=0.9,
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
            
            # Save results
            storage.save_result(result1)
            storage.save_result(result2)
            storage.save_result(result3)
            
            # Get matched runs
            matched = storage.get_matched_runs(["gpt-4", "baseline"])
            
            # Should have task1 with both testees
            assert "task1" in matched
            assert "gpt-4" in matched["task1"]
            assert "baseline" in matched["task1"]
            assert matched["task1"]["gpt-4"].run_id == "run1"
            assert matched["task1"]["baseline"].run_id == "run2"
            
            # task2 only has gpt-4, so should not be included
            assert "task2" not in matched
