"""
Unit tests for LeaderboardManager class.

Tests initialization, adding runs, duplicate handling, and persistence.
"""
import pytest
import tempfile
import json
from datetime import datetime, timezone
from pathlib import Path

from benchmark.analysis.leaderboard import (
    LeaderboardManager,
    METRICS,
    PROPERTY_TYPES,
    EVALUATION_MODES,
)
from benchmark.models.leaderboard import LeaderboardEntry, Leaderboard
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


def create_mock_benchmark_result(
    run_id: str,
    task_id: str,
    testee_id: str,
    completeness: float = 0.9,
    robustness: float = 0.85,
    syntactic_validity: float = 0.95,
    final_score: float = 0.9,
    evaluation_mode: str = "single_turn",
) -> BenchmarkResult:
    """Create a mock BenchmarkResult for testing."""
    return BenchmarkResult(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
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


def create_mock_property_result(
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
        },
    )


def create_mock_run_result(
    run_id: str = "run_20260101_120000_abc123",
    testee_id: str = "dagent",
    evaluation_mode: str = "single_turn",
    model_version: str = None,
    property_types: list[str] = None,
    avg_score: float = 0.85,
) -> BenchmarkRunResult:
    """Create a mock BenchmarkRunResult for testing."""
    if property_types is None:
        property_types = ["reachability"]
    
    property_results = {}
    for prop_type in property_types:
        task_result = create_mock_benchmark_result(
            run_id=f"{run_id}_{prop_type}",
            task_id=f"{prop_type}_task_001",
            testee_id=testee_id,
            final_score=avg_score,
            evaluation_mode=evaluation_mode,
        )
        property_results[prop_type] = create_mock_property_result(
            property_type=prop_type,
            results=[task_result],
        )
    
    return BenchmarkRunResult(
        run_id=run_id,
        testee_id=testee_id,
        testee_type="llm",
        evaluation_mode=evaluation_mode,
        model_version=model_version,
        timestamp=datetime.now(timezone.utc),
        property_results=property_results,
        total_tasks=len(property_types),
        overall_average_score=avg_score,
        execution_time_seconds=60.0,
    )


# ============================================================================
# Initialization Tests
# ============================================================================


class TestLeaderboardManagerInit:
    """Tests for LeaderboardManager initialization."""

    def test_init_empty(self):
        """Test creating empty manager."""
        manager = LeaderboardManager()
        
        assert manager.collection is not None
        assert len(manager.list_leaderboard_ids()) == 0

    def test_init_with_path_nonexistent(self, tmp_path):
        """Test creating manager with nonexistent path doesn't error."""
        path = tmp_path / "leaderboards.json"
        manager = LeaderboardManager(leaderboards_path=str(path))
        
        assert len(manager.list_leaderboard_ids()) == 0

    def test_init_with_path_existing(self, tmp_path):
        """Test creating manager with existing file loads it."""
        path = tmp_path / "leaderboards.json"
        
        # Create a manager, initialize, and save
        manager1 = LeaderboardManager()
        manager1.initialize_leaderboards()
        manager1.save_leaderboards(str(path))
        
        # Create new manager with same path
        manager2 = LeaderboardManager(leaderboards_path=str(path))
        
        assert len(manager2.list_leaderboard_ids()) > 0


# ============================================================================
# Initialize Leaderboards Tests
# ============================================================================


class TestInitializeLeaderboards:
    """Tests for initialize_leaderboards method."""

    def test_creates_standard_leaderboards(self):
        """Test that all standard leaderboards are created."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        ids = manager.list_leaderboard_ids()
        
        # Check overall leaderboards
        assert "overall_single_turn" in ids
        assert "overall_multi_turn" in ids
        
        # Check per-metric leaderboards
        for metric in ["completeness", "robustness", "syntactic_validity"]:
            assert f"{metric}_single_turn" in ids
            assert f"{metric}_multi_turn" in ids
        
        # Check per-property leaderboards
        for prop_type in PROPERTY_TYPES:
            assert f"{prop_type}_single_turn" in ids
            assert f"{prop_type}_multi_turn" in ids

    def test_creates_correct_number_of_leaderboards(self):
        """Test that correct total number of leaderboards is created."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        ids = manager.list_leaderboard_ids()
        
        # overall: 2 (single_turn, multi_turn)
        # per-metric: 3 metrics × 2 modes = 6
        # per-property: 3 properties × 2 modes = 6
        # Total: 2 + 6 + 6 = 14
        assert len(ids) == 14

    def test_leaderboards_are_empty(self):
        """Test that initialized leaderboards have no entries."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        for lb_id in manager.list_leaderboard_ids():
            lb = manager.get_leaderboard(lb_id)
            assert len(lb.entries) == 0

    def test_leaderboard_metadata(self):
        """Test that leaderboard metadata is set correctly."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        # Check overall_single_turn
        lb = manager.get_leaderboard("overall_single_turn")
        assert lb.name == "Overall (Single-Turn)"
        assert lb.evaluation_mode == "single_turn"
        assert lb.metric_name == "overall"
        assert lb.property_type is None
        
        # Check reachability_multi_turn
        lb = manager.get_leaderboard("reachability_multi_turn")
        assert lb.evaluation_mode == "multi_turn"
        assert lb.metric_name == "overall"
        assert lb.property_type == "reachability"


# ============================================================================
# Add Benchmark Run Tests
# ============================================================================


class TestAddBenchmarkRun:
    """Tests for add_benchmark_run method."""

    def test_adds_to_overall_leaderboard(self):
        """Test that run is added to overall leaderboard."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        run = create_mock_run_result(
            testee_id="dagent",
            evaluation_mode="single_turn",
            avg_score=0.85,
        )
        
        updated = manager.add_benchmark_run(run)
        
        assert "overall_single_turn" in updated
        
        lb = manager.get_leaderboard("overall_single_turn")
        assert len(lb.entries) == 1
        assert lb.entries[0].testee_id == "dagent"
        assert lb.entries[0].score == 0.85

    def test_adds_to_metric_leaderboards(self):
        """Test that run is added to per-metric leaderboards."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        run = create_mock_run_result(
            testee_id="gpt-4o",
            evaluation_mode="single_turn",
        )
        
        updated = manager.add_benchmark_run(run)
        
        # Should be added to completeness, robustness, syntactic_validity
        assert "completeness_single_turn" in updated
        assert "robustness_single_turn" in updated
        assert "syntactic_validity_single_turn" in updated

    def test_adds_to_property_leaderboards(self):
        """Test that run is added to property-specific leaderboards."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        run = create_mock_run_result(
            testee_id="dagent",
            evaluation_mode="single_turn",
            property_types=["reachability", "bgp_configuration"],
        )
        
        updated = manager.add_benchmark_run(run)
        
        assert "reachability_single_turn" in updated
        assert "bgp_configuration_single_turn" in updated
        # ospf should NOT be added since it wasn't in the run
        assert "ospf_configuration_single_turn" not in updated

    def test_multi_turn_goes_to_multi_turn_leaderboards(self):
        """Test that multi-turn runs go to multi-turn leaderboards."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        run = create_mock_run_result(
            testee_id="dagent",
            evaluation_mode="multi_turn",
            avg_score=0.90,
        )
        
        updated = manager.add_benchmark_run(run)
        
        # Should be in multi_turn
        assert "overall_multi_turn" in updated
        assert "completeness_multi_turn" in updated
        
        # Should NOT be in single_turn
        assert "overall_single_turn" not in updated
        assert "completeness_single_turn" not in updated

    def test_entry_includes_breakdown(self):
        """Test that entry includes score breakdown."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        run = create_mock_run_result(testee_id="dagent")
        manager.add_benchmark_run(run)
        
        lb = manager.get_leaderboard("overall_single_turn")
        entry = lb.entries[0]
        
        assert entry.breakdown is not None
        assert "completeness" in entry.breakdown
        assert "robustness" in entry.breakdown
        assert "syntactic_validity" in entry.breakdown

    def test_entry_includes_model_version(self):
        """Test that entry includes model version when available."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        run = create_mock_run_result(
            testee_id="dagent",
            model_version="gpt-4-0125-preview",
        )
        manager.add_benchmark_run(run)
        
        lb = manager.get_leaderboard("overall_single_turn")
        entry = lb.entries[0]
        
        assert entry.model_version == "gpt-4-0125-preview"


# ============================================================================
# Duplicate Handling Tests
# ============================================================================


class TestDuplicateHandling:
    """Tests for handling duplicate testee entries."""

    def test_keeps_most_recent_entry(self):
        """Test that most recent entry is kept for duplicate testee."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        # Add first run
        run1 = create_mock_run_result(
            run_id="run_old",
            testee_id="dagent",
            avg_score=0.75,
        )
        manager.add_benchmark_run(run1)
        
        # Add newer run (will have later timestamp)
        run2 = create_mock_run_result(
            run_id="run_new",
            testee_id="dagent",
            avg_score=0.90,
        )
        manager.add_benchmark_run(run2)
        
        lb = manager.get_leaderboard("overall_single_turn")
        
        # Should only have one entry
        assert len(lb.entries) == 1
        # Should be the newer run with higher score
        assert lb.entries[0].run_id == "run_new"
        assert lb.entries[0].score == 0.90

    def test_multiple_testees_maintained(self):
        """Test that different testees have separate entries."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        for testee in ["dagent", "gpt-4o", "claude-3"]:
            run = create_mock_run_result(
                run_id=f"run_{testee}",
                testee_id=testee,
                avg_score=0.85,
            )
            manager.add_benchmark_run(run)
        
        lb = manager.get_leaderboard("overall_single_turn")
        
        assert len(lb.entries) == 3
        testees = {e.testee_id for e in lb.entries}
        assert testees == {"dagent", "gpt-4o", "claude-3"}

    def test_maintains_sort_order_after_updates(self):
        """Test that sort order is maintained after duplicate updates."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        # Add three testees
        for testee, score in [("low", 0.60), ("mid", 0.75), ("high", 0.90)]:
            run = create_mock_run_result(
                run_id=f"run_{testee}_1",
                testee_id=testee,
                avg_score=score,
            )
            manager.add_benchmark_run(run)
        
        # Update "low" to have highest score
        run = create_mock_run_result(
            run_id="run_low_2",
            testee_id="low",
            avg_score=0.95,
        )
        manager.add_benchmark_run(run)
        
        lb = manager.get_leaderboard("overall_single_turn")
        
        # "low" should now be first
        assert lb.entries[0].testee_id == "low"
        assert lb.entries[0].score == 0.95


# ============================================================================
# Persistence Tests
# ============================================================================


class TestPersistence:
    """Tests for save/load functionality."""

    def test_save_leaderboards(self, tmp_path):
        """Test saving leaderboards to file."""
        path = tmp_path / "leaderboards.json"
        
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        # Add some data
        run = create_mock_run_result(testee_id="dagent", avg_score=0.85)
        manager.add_benchmark_run(run)
        
        # Save
        saved_path = manager.save_leaderboards(str(path))
        
        assert Path(saved_path).exists()
        
        # Verify content
        with open(path) as f:
            data = json.load(f)
        
        assert "leaderboards" in data
        assert "overall_single_turn" in data["leaderboards"]

    def test_load_leaderboards(self, tmp_path):
        """Test loading leaderboards from file."""
        path = tmp_path / "leaderboards.json"
        
        # Create and save
        manager1 = LeaderboardManager()
        manager1.initialize_leaderboards()
        run = create_mock_run_result(testee_id="dagent", avg_score=0.85)
        manager1.add_benchmark_run(run)
        manager1.save_leaderboards(str(path))
        
        # Load into new manager
        manager2 = LeaderboardManager()
        manager2.load_leaderboards(str(path))
        
        # Verify data
        lb = manager2.get_leaderboard("overall_single_turn")
        assert lb is not None
        assert len(lb.entries) == 1
        assert lb.entries[0].testee_id == "dagent"

    def test_save_without_path_raises(self):
        """Test that save without path raises error."""
        manager = LeaderboardManager()
        manager.initialize_leaderboards()
        
        with pytest.raises(ValueError) as exc_info:
            manager.save_leaderboards()
        
        assert "No path provided" in str(exc_info.value)

    def test_load_without_path_raises(self):
        """Test that load without path raises error."""
        manager = LeaderboardManager()
        
        with pytest.raises(ValueError) as exc_info:
            manager.load_leaderboards()
        
        assert "No path provided" in str(exc_info.value)

    def test_roundtrip_preserves_data(self, tmp_path):
        """Test that save/load preserves all data."""
        path = tmp_path / "leaderboards.json"
        
        # Create manager with data
        manager1 = LeaderboardManager()
        manager1.initialize_leaderboards()
        
        # Add multiple runs
        for testee, score in [("dagent", 0.85), ("gpt-4o", 0.90), ("claude-3", 0.80)]:
            run = create_mock_run_result(
                run_id=f"run_{testee}",
                testee_id=testee,
                model_version=f"{testee}-v1",
                avg_score=score,
            )
            manager1.add_benchmark_run(run)
        
        # Save and reload
        manager1.save_leaderboards(str(path))
        
        manager2 = LeaderboardManager()
        manager2.load_leaderboards(str(path))
        
        # Verify all data preserved
        lb1 = manager1.get_leaderboard("overall_single_turn")
        lb2 = manager2.get_leaderboard("overall_single_turn")
        
        assert len(lb1.entries) == len(lb2.entries)
        
        for e1, e2 in zip(lb1.entries, lb2.entries):
            assert e1.testee_id == e2.testee_id
            assert e1.score == e2.score
            assert e1.model_version == e2.model_version
