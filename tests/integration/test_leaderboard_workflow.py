"""
Integration tests for leaderboard workflow.

Tests the complete leaderboard lifecycle:
- Initialize leaderboards
- Create mock benchmark runs for multiple testees
- Add runs to leaderboards
- Verify correct placement and ordering
- Save/load persistence
- Verify data integrity
"""
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from benchmark.storage import ResultsStorage
from benchmark.analysis.leaderboard import LeaderboardManager
from benchmark.models.leaderboard import LeaderboardEntry
from benchmark.models.results import (
    BenchmarkRunResult,
    PropertyExecutionResult,
    BenchmarkResult,
    ScoringResult,
    ValidityCheck,
    ExecutionMetrics,
    PropertyEvaluationResult,
)


# ============================================================================
# Test Fixtures
# ============================================================================


def create_benchmark_result(
    run_id: str,
    task_id: str,
    testee_id: str,
    completeness: float = 0.9,
    robustness: float = 0.85,
    syntactic_validity: float = 0.95,
    final_score: float = 0.9,
    evaluation_mode: str = "single_turn",
    timestamp: datetime = None,
) -> BenchmarkResult:
    """Create a mock BenchmarkResult."""
    return BenchmarkResult(
        run_id=run_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        task_id=task_id,
        testee_id=testee_id,
        testee_type="llm",
        evaluation_mode=evaluation_mode,
        success=True,
        property_results=[
            PropertyEvaluationResult(
                property_id="prop_1",
                satisfied=True,
                observation_raw="OK",
                evaluation_time_seconds=1.0,
            )
        ],
        scoring=ScoringResult(
            completeness=completeness,
            robustness=robustness,
            syntactic_validity=syntactic_validity,
            final_score=final_score,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.3},
        ),
        validity=ValidityCheck(
            is_valid_solution=final_score >= 0.8,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        ),
        metrics=ExecutionMetrics(
            infrastructure_provision_time=5.0,
            config_execution_time=2.0,
            convergence_time=10.0,
            evaluation_time=1.0,
            total_time=18.0,
        ),
    )


def create_property_result(
    property_type: str,
    results: list[BenchmarkResult],
) -> PropertyExecutionResult:
    """Create a mock PropertyExecutionResult."""
    total_score = sum(r.scoring.final_score for r in results) / len(results) if results else 0.0
    return PropertyExecutionResult(
        property_type=property_type,
        total_tasks=len(results),
        successful_tasks=sum(1 for r in results if r.success),
        results=results,
        average_score=total_score,
        aggregate_metrics={
            "completeness": sum(r.scoring.completeness for r in results) / len(results) if results else 0.0,
            "robustness": sum(r.scoring.robustness for r in results) / len(results) if results else 0.0,
            "syntactic_validity": sum(r.scoring.syntactic_validity for r in results) / len(results) if results else 0.0,
        },
    )


def create_benchmark_run(
    run_id: str,
    testee_id: str,
    model_version: str = None,
    evaluation_mode: str = "single_turn",
    property_types: list[str] = None,
    overall_score: float = 0.85,
    timestamp: datetime = None,
) -> BenchmarkRunResult:
    """Create a mock BenchmarkRunResult."""
    if property_types is None:
        property_types = ["reachability"]
    
    property_results = {}
    for prop_type in property_types:
        task_result = create_benchmark_result(
            run_id=f"{run_id}_{prop_type}",
            task_id=f"{prop_type}_task_001",
            testee_id=testee_id,
            final_score=overall_score,
            evaluation_mode=evaluation_mode,
            timestamp=timestamp,
        )
        property_results[prop_type] = create_property_result(
            property_type=prop_type,
            results=[task_result],
        )
    
    return BenchmarkRunResult(
        run_id=run_id,
        testee_id=testee_id,
        testee_type="llm",
        evaluation_mode=evaluation_mode,
        model_version=model_version,
        timestamp=timestamp or datetime.now(timezone.utc),
        property_results=property_results,
        total_tasks=len(property_types),
        overall_average_score=overall_score,
        execution_time_seconds=60.0,
    )


# ============================================================================
# Integration Tests
# ============================================================================


class TestLeaderboardWorkflow:
    """End-to-end integration tests for leaderboard workflow."""

    def test_complete_workflow(self, tmp_path):
        """Test complete leaderboard workflow from init to verify."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        # Step 1: Initialize leaderboards
        manager = storage.get_leaderboard_manager()
        manager.initialize_leaderboards()
        manager.save_leaderboards()
        
        assert len(manager.list_leaderboard_ids()) == 14
        
        # Step 2: Create mock runs for multiple testees
        testee_runs = [
            ("dagent", "gpt-4o-2024-05-13", 0.92),
            ("gpt-4o", None, 0.88),
            ("claude-3-sonnet", None, 0.85),
            ("baseline", None, 0.20),
        ]
        
        for testee_id, model_version, score in testee_runs:
            run = create_benchmark_run(
                run_id=f"run_{testee_id}_20260103",
                testee_id=testee_id,
                model_version=model_version,
                overall_score=score,
                property_types=["reachability", "bgp_configuration"],
            )
            manager.add_benchmark_run(run)
        
        # Step 3: Verify correct placement and ordering
        overall_lb = manager.get_leaderboard("overall_single_turn")
        
        assert len(overall_lb.entries) == 4
        
        # Should be ordered by score descending
        assert overall_lb.entries[0].testee_id == "dagent"
        assert overall_lb.entries[0].score == 0.92
        assert overall_lb.entries[1].testee_id == "gpt-4o"
        assert overall_lb.entries[2].testee_id == "claude-3-sonnet"
        assert overall_lb.entries[3].testee_id == "baseline"
        
        # Check ranks
        assert overall_lb.get_rank("dagent") == 1
        assert overall_lb.get_rank("gpt-4o") == 2
        assert overall_lb.get_rank("baseline") == 4
        
        # Step 4: Save to file
        saved_path = manager.save_leaderboards()
        assert Path(saved_path).exists()
        
        # Step 5: Load from file in new manager
        manager2 = LeaderboardManager(leaderboards_path=saved_path)
        
        # Step 6: Verify data integrity
        overall_lb2 = manager2.get_leaderboard("overall_single_turn")
        
        assert len(overall_lb2.entries) == 4
        assert overall_lb2.entries[0].testee_id == "dagent"
        assert overall_lb2.entries[0].score == 0.92
        assert overall_lb2.entries[0].model_version == "gpt-4o-2024-05-13"

    def test_duplicate_handling_workflow(self, tmp_path):
        """Test that duplicate entries are handled correctly (newest wins)."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        manager = storage.get_leaderboard_manager()
        manager.initialize_leaderboards()
        
        base_time = datetime.now(timezone.utc)
        
        # Add initial run for dagent with score 0.80
        run1 = create_benchmark_run(
            run_id="run_dagent_old",
            testee_id="dagent",
            overall_score=0.80,
            timestamp=base_time - timedelta(hours=1),
        )
        manager.add_benchmark_run(run1)
        
        # Add newer run for dagent with score 0.90
        run2 = create_benchmark_run(
            run_id="run_dagent_new",
            testee_id="dagent",
            overall_score=0.90,
            timestamp=base_time,
        )
        manager.add_benchmark_run(run2)
        
        overall_lb = manager.get_leaderboard("overall_single_turn")
        
        # Should only have one entry (the newer one)
        assert len(overall_lb.entries) == 1
        assert overall_lb.entries[0].run_id == "run_dagent_new"
        assert overall_lb.entries[0].score == 0.90

    def test_multi_turn_vs_single_turn_separation(self, tmp_path):
        """Test that single-turn and multi-turn runs go to separate leaderboards."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        manager = storage.get_leaderboard_manager()
        manager.initialize_leaderboards()
        
        # Add single-turn run
        single_run = create_benchmark_run(
            run_id="run_single",
            testee_id="dagent",
            evaluation_mode="single_turn",
            overall_score=0.85,
        )
        manager.add_benchmark_run(single_run)
        
        # Add multi-turn run
        multi_run = create_benchmark_run(
            run_id="run_multi",
            testee_id="dagent",
            evaluation_mode="multi_turn",
            overall_score=0.90,
        )
        manager.add_benchmark_run(multi_run)
        
        # Check single-turn leaderboard
        single_lb = manager.get_leaderboard("overall_single_turn")
        assert len(single_lb.entries) == 1
        assert single_lb.entries[0].score == 0.85
        
        # Check multi-turn leaderboard
        multi_lb = manager.get_leaderboard("overall_multi_turn")
        assert len(multi_lb.entries) == 1
        assert multi_lb.entries[0].score == 0.90

    def test_property_specific_leaderboards(self, tmp_path):
        """Test that property-specific leaderboards are populated correctly."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        manager = storage.get_leaderboard_manager()
        manager.initialize_leaderboards()
        
        # Add run with only reachability property
        reachability_run = create_benchmark_run(
            run_id="run_reach",
            testee_id="testee_reach",
            property_types=["reachability"],
            overall_score=0.95,
        )
        manager.add_benchmark_run(reachability_run)
        
        # Add run with only bgp property
        bgp_run = create_benchmark_run(
            run_id="run_bgp",
            testee_id="testee_bgp",
            property_types=["bgp_configuration"],
            overall_score=0.85,
        )
        manager.add_benchmark_run(bgp_run)
        
        # Check reachability leaderboard
        reach_lb = manager.get_leaderboard("reachability_single_turn")
        assert len(reach_lb.entries) == 1
        assert reach_lb.entries[0].testee_id == "testee_reach"
        
        # Check BGP leaderboard
        bgp_lb = manager.get_leaderboard("bgp_configuration_single_turn")
        assert len(bgp_lb.entries) == 1
        assert bgp_lb.entries[0].testee_id == "testee_bgp"
        
        # Check overall has both
        overall_lb = manager.get_leaderboard("overall_single_turn")
        assert len(overall_lb.entries) == 2

    def test_persistence_with_storage_integration(self, tmp_path):
        """Test that storage integration works correctly."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        # Initialize and populate
        manager = storage.get_leaderboard_manager()
        manager.initialize_leaderboards()
        
        run = create_benchmark_run(
            run_id="run_test",
            testee_id="dagent",
            model_version="gpt-4o",
            overall_score=0.88,
        )
        manager.add_benchmark_run(run)
        manager.save_leaderboards()
        
        # Save the run to storage as well
        storage.save_benchmark_run(run)
        
        # Create new storage instance (simulating app restart)
        storage2 = ResultsStorage(base_dir=str(tmp_path))
        
        # Load via storage
        collection = storage2.load_leaderboards()
        assert collection is not None
        
        overall_lb = collection.get_leaderboard("overall_single_turn")
        assert len(overall_lb.entries) == 1
        assert overall_lb.entries[0].testee_id == "dagent"
        
        # Verify benchmark run is also loaded
        runs = storage2.list_benchmark_runs()
        assert "run_test" in runs


class TestLeaderboardCLIIntegration:
    """Integration tests for CLI commands working together."""

    def test_cli_workflow(self, tmp_path):
        """Test CLI commands working in sequence."""
        from click.testing import CliRunner
        from benchmark.cli import main
        
        runner = CliRunner()
        output_dir = str(tmp_path)
        
        # 1. Initialize
        result = runner.invoke(main, [
            "leaderboard", "init", "--output-dir", output_dir
        ])
        assert result.exit_code == 0
        assert "14 standard leaderboards" in result.output
        
        # 2. List
        result = runner.invoke(main, [
            "leaderboard", "list", "--output-dir", output_dir
        ])
        assert result.exit_code == 0
        assert "overall_single_turn" in result.output
        
        # 3. Show (empty)
        result = runner.invoke(main, [
            "leaderboard", "show", "overall_single_turn",
            "--output-dir", output_dir
        ])
        assert result.exit_code == 0
        assert "No entries yet" in result.output
        
        # 4. Export
        export_path = tmp_path / "export.json"
        result = runner.invoke(main, [
            "leaderboard", "export", "--output", str(export_path),
            "--output-dir", output_dir
        ])
        assert result.exit_code == 0
        assert export_path.exists()
