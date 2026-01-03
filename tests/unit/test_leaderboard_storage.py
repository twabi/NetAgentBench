"""
Unit tests for leaderboard storage integration.

Tests the leaderboard-related methods in ResultsStorage.
"""
import pytest
import json
from datetime import datetime, timezone
from pathlib import Path

from benchmark.storage import ResultsStorage
from benchmark.models.leaderboard import (
    LeaderboardEntry,
    Leaderboard,
    LeaderboardCollection,
)


class TestLeaderboardStorageIntegration:
    """Tests for ResultsStorage leaderboard methods."""

    def test_leaderboards_path(self, tmp_path):
        """Test leaderboards_path property."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        expected = tmp_path / "leaderboards.json"
        assert storage.leaderboards_path == expected

    def test_save_leaderboards(self, tmp_path):
        """Test saving leaderboards to disk."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        # Create a collection with some data
        collection = LeaderboardCollection()
        lb = Leaderboard(
            leaderboard_id="test_lb",
            name="Test Leaderboard",
            description="For testing",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        entry = LeaderboardEntry(
            testee_id="dagent",
            score=0.85,
            run_id="run_123",
            timestamp=datetime.now(timezone.utc),
            num_tasks=10,
        )
        lb.add_entry(entry)
        collection.add_leaderboard(lb)
        
        # Save
        saved_path = storage.save_leaderboards(collection)
        
        # Verify file exists
        assert Path(saved_path).exists()
        
        # Verify content
        with open(saved_path) as f:
            data = json.load(f)
        
        assert "leaderboards" in data
        assert "test_lb" in data["leaderboards"]

    def test_load_leaderboards_exists(self, tmp_path):
        """Test loading leaderboards from disk."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        # Create and save a collection
        collection = LeaderboardCollection()
        lb = Leaderboard(
            leaderboard_id="overall_single_turn",
            name="Overall Single-Turn",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        entry = LeaderboardEntry(
            testee_id="gpt-4o",
            score=0.90,
            run_id="run_456",
            timestamp=datetime.now(timezone.utc),
            num_tasks=5,
        )
        lb.add_entry(entry)
        collection.add_leaderboard(lb)
        storage.save_leaderboards(collection)
        
        # Load
        loaded = storage.load_leaderboards()
        
        assert loaded is not None
        assert "overall_single_turn" in loaded.leaderboards
        
        lb_loaded = loaded.get_leaderboard("overall_single_turn")
        assert len(lb_loaded.entries) == 1
        assert lb_loaded.entries[0].testee_id == "gpt-4o"

    def test_load_leaderboards_not_exists(self, tmp_path):
        """Test loading when no leaderboards file exists."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        loaded = storage.load_leaderboards()
        
        assert loaded is None

    def test_get_leaderboard_manager_new(self, tmp_path):
        """Test getting manager when no leaderboards exist."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        manager = storage.get_leaderboard_manager()
        
        assert manager is not None
        assert len(manager.list_leaderboard_ids()) == 0

    def test_get_leaderboard_manager_existing(self, tmp_path):
        """Test getting manager with existing leaderboards."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        # Create and save a collection
        collection = LeaderboardCollection()
        lb = Leaderboard(
            leaderboard_id="test_lb",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        collection.add_leaderboard(lb)
        storage.save_leaderboards(collection)
        
        # Get manager (should load existing)
        manager = storage.get_leaderboard_manager()
        
        assert "test_lb" in manager.list_leaderboard_ids()

    def test_list_benchmark_runs_empty(self, tmp_path):
        """Test listing runs when none exist."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        runs = storage.list_benchmark_runs()
        
        assert runs == []


class TestLeaderboardStorageRoundtrip:
    """Tests for complete save/load roundtrips."""

    def test_full_roundtrip_with_entries(self, tmp_path):
        """Test save/load preserves all data including entries."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        # Create collection with multiple leaderboards and entries
        collection = LeaderboardCollection()
        
        for mode in ["single_turn", "multi_turn"]:
            lb = Leaderboard(
                leaderboard_id=f"overall_{mode}",
                name=f"Overall ({mode})",
                description="Test",
                evaluation_mode=mode,
                metric_name="overall",
            )
            
            # Add multiple entries
            for i, (testee, score) in enumerate([
                ("dagent", 0.90),
                ("gpt-4o", 0.85),
                ("claude-3", 0.80),
            ]):
                entry = LeaderboardEntry(
                    testee_id=testee,
                    score=score,
                    run_id=f"run_{mode}_{i}",
                    timestamp=datetime.now(timezone.utc),
                    num_tasks=10,
                    breakdown={"completeness": 0.95, "robustness": 0.85},
                )
                lb.add_entry(entry)
            
            collection.add_leaderboard(lb)
        
        # Save
        storage.save_leaderboards(collection)
        
        # Load in new storage instance
        storage2 = ResultsStorage(base_dir=str(tmp_path))
        loaded = storage2.load_leaderboards()
        
        # Verify
        assert len(loaded.leaderboards) == 2
        
        for mode in ["single_turn", "multi_turn"]:
            lb = loaded.get_leaderboard(f"overall_{mode}")
            assert len(lb.entries) == 3
            
            # Check ordering (should be by score descending)
            assert lb.entries[0].testee_id == "dagent"
            assert lb.entries[1].testee_id == "gpt-4o"
            assert lb.entries[2].testee_id == "claude-3"
            
            # Check breakdown preserved
            assert lb.entries[0].breakdown["completeness"] == 0.95
