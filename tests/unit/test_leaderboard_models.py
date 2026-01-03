"""
Unit tests for leaderboard data models.

Tests LeaderboardEntry, Leaderboard, and LeaderboardCollection classes.
"""
import pytest
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

from benchmark.models.leaderboard import (
    LeaderboardEntry,
    Leaderboard,
    LeaderboardCollection,
)


# ============================================================================
# LeaderboardEntry Tests
# ============================================================================


class TestLeaderboardEntry:
    """Tests for LeaderboardEntry model."""

    def test_entry_creation_minimal(self):
        """Test creating entry with required fields only."""
        entry = LeaderboardEntry(
            testee_id="dagent",
            score=0.85,
            run_id="run_20260101_120000_abc123",
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
            num_tasks=10,
        )
        
        assert entry.testee_id == "dagent"
        assert entry.score == 0.85
        assert entry.run_id == "run_20260101_120000_abc123"
        assert entry.num_tasks == 10
        assert entry.model_version is None
        assert entry.breakdown is None

    def test_entry_creation_full(self):
        """Test creating entry with all fields."""
        entry = LeaderboardEntry(
            testee_id="gpt-4o",
            model_version="gpt-4-0125-preview",
            score=0.92,
            run_id="run_20260101_130000_def456",
            timestamp=datetime(2026, 1, 1, 13, 0, 0),
            num_tasks=15,
            breakdown={
                "completeness": 0.95,
                "robustness": 0.88,
                "syntactic_validity": 0.93,
            },
        )
        
        assert entry.testee_id == "gpt-4o"
        assert entry.model_version == "gpt-4-0125-preview"
        assert entry.score == 0.92
        assert entry.breakdown["completeness"] == 0.95

    def test_entry_score_validation_low(self):
        """Test that score below 0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LeaderboardEntry(
                testee_id="test",
                score=-0.1,
                run_id="run_123",
                timestamp=datetime.now(timezone.utc),
                num_tasks=5,
            )
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_entry_score_validation_high(self):
        """Test that score above 1 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LeaderboardEntry(
                testee_id="test",
                score=1.5,
                run_id="run_123",
                timestamp=datetime.now(timezone.utc),
                num_tasks=5,
            )
        assert "less than or equal to 1" in str(exc_info.value)

    def test_entry_score_boundary_values(self):
        """Test that score boundary values 0 and 1 are accepted."""
        entry_0 = LeaderboardEntry(
            testee_id="test",
            score=0.0,
            run_id="run_123",
            timestamp=datetime.now(timezone.utc),
            num_tasks=5,
        )
        entry_1 = LeaderboardEntry(
            testee_id="test",
            score=1.0,
            run_id="run_124",
            timestamp=datetime.now(timezone.utc),
            num_tasks=5,
        )
        
        assert entry_0.score == 0.0
        assert entry_1.score == 1.0

    def test_entry_breakdown_validation_invalid_score(self):
        """Test that breakdown with invalid score is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LeaderboardEntry(
                testee_id="test",
                score=0.8,
                run_id="run_123",
                timestamp=datetime.now(timezone.utc),
                num_tasks=5,
                breakdown={"completeness": 1.5},
            )
        assert "between 0 and 1" in str(exc_info.value)

    def test_entry_num_tasks_validation(self):
        """Test that negative num_tasks is rejected."""
        with pytest.raises(ValidationError):
            LeaderboardEntry(
                testee_id="test",
                score=0.8,
                run_id="run_123",
                timestamp=datetime.now(timezone.utc),
                num_tasks=-1,
            )


# ============================================================================
# Leaderboard Tests
# ============================================================================


class TestLeaderboard:
    """Tests for Leaderboard model."""

    def test_leaderboard_creation(self):
        """Test creating a leaderboard."""
        lb = Leaderboard(
            leaderboard_id="overall_single_turn",
            name="Overall Single-Turn Leaderboard",
            description="Ranks testees by overall score in single-turn mode",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        assert lb.leaderboard_id == "overall_single_turn"
        assert lb.name == "Overall Single-Turn Leaderboard"
        assert lb.evaluation_mode == "single_turn"
        assert lb.metric_name == "overall"
        assert lb.property_type is None
        assert lb.entries == []

    def test_leaderboard_with_property_type(self):
        """Test creating a property-specific leaderboard."""
        lb = Leaderboard(
            leaderboard_id="reachability_single_turn",
            name="Reachability Single-Turn Leaderboard",
            description="Ranks testees by reachability performance",
            evaluation_mode="single_turn",
            metric_name="overall",
            property_type="reachability",
        )
        
        assert lb.property_type == "reachability"

    def test_leaderboard_evaluation_mode_validation(self):
        """Test that invalid evaluation_mode is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Leaderboard(
                leaderboard_id="test",
                name="Test",
                description="Test",
                evaluation_mode="invalid_mode",
                metric_name="overall",
            )
        assert "evaluation_mode must be one of" in str(exc_info.value)

    def test_leaderboard_add_entry_empty(self):
        """Test adding first entry to empty leaderboard."""
        lb = Leaderboard(
            leaderboard_id="test",
            name="Test",
            description="Test",
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
        
        assert len(lb.entries) == 1
        assert lb.entries[0].testee_id == "dagent"

    def test_leaderboard_add_entry_maintains_sort(self):
        """Test that entries are maintained in descending score order."""
        lb = Leaderboard(
            leaderboard_id="test",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        now = datetime.now(timezone.utc)
        
        # Add entries out of order
        lb.add_entry(LeaderboardEntry(
            testee_id="low", score=0.60, run_id="run_1",
            timestamp=now, num_tasks=5,
        ))
        lb.add_entry(LeaderboardEntry(
            testee_id="high", score=0.95, run_id="run_2",
            timestamp=now, num_tasks=5,
        ))
        lb.add_entry(LeaderboardEntry(
            testee_id="mid", score=0.75, run_id="run_3",
            timestamp=now, num_tasks=5,
        ))
        
        assert len(lb.entries) == 3
        assert lb.entries[0].testee_id == "high"
        assert lb.entries[1].testee_id == "mid"
        assert lb.entries[2].testee_id == "low"

    def test_leaderboard_add_entry_duplicate_keeps_newest(self):
        """Test that duplicate testee is replaced with newer entry."""
        lb = Leaderboard(
            leaderboard_id="test",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        old_time = datetime(2026, 1, 1, 12, 0, 0)
        new_time = datetime(2026, 1, 2, 12, 0, 0)
        
        # Add old entry
        lb.add_entry(LeaderboardEntry(
            testee_id="dagent", score=0.80, run_id="run_old",
            timestamp=old_time, num_tasks=5,
        ))
        
        # Add newer entry for same testee
        lb.add_entry(LeaderboardEntry(
            testee_id="dagent", score=0.90, run_id="run_new",
            timestamp=new_time, num_tasks=10,
        ))
        
        assert len(lb.entries) == 1
        assert lb.entries[0].run_id == "run_new"
        assert lb.entries[0].score == 0.90

    def test_leaderboard_add_entry_duplicate_keeps_existing_if_older(self):
        """Test that older duplicate is ignored."""
        lb = Leaderboard(
            leaderboard_id="test",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        old_time = datetime(2026, 1, 1, 12, 0, 0)
        new_time = datetime(2026, 1, 2, 12, 0, 0)
        
        # Add new entry first
        lb.add_entry(LeaderboardEntry(
            testee_id="dagent", score=0.90, run_id="run_new",
            timestamp=new_time, num_tasks=10,
        ))
        
        # Add older entry for same testee (should be ignored)
        lb.add_entry(LeaderboardEntry(
            testee_id="dagent", score=0.70, run_id="run_old",
            timestamp=old_time, num_tasks=5,
        ))
        
        assert len(lb.entries) == 1
        assert lb.entries[0].run_id == "run_new"
        assert lb.entries[0].score == 0.90

    def test_leaderboard_get_rank(self):
        """Test getting rank of a testee."""
        lb = Leaderboard(
            leaderboard_id="test",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        now = datetime.now(timezone.utc)
        lb.add_entry(LeaderboardEntry(
            testee_id="first", score=0.95, run_id="run_1",
            timestamp=now, num_tasks=5,
        ))
        lb.add_entry(LeaderboardEntry(
            testee_id="second", score=0.85, run_id="run_2",
            timestamp=now, num_tasks=5,
        ))
        lb.add_entry(LeaderboardEntry(
            testee_id="third", score=0.75, run_id="run_3",
            timestamp=now, num_tasks=5,
        ))
        
        assert lb.get_rank("first") == 1
        assert lb.get_rank("second") == 2
        assert lb.get_rank("third") == 3
        assert lb.get_rank("nonexistent") is None

    def test_leaderboard_get_top_n(self):
        """Test getting top N entries."""
        lb = Leaderboard(
            leaderboard_id="test",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        now = datetime.now(timezone.utc)
        for i in range(5):
            lb.add_entry(LeaderboardEntry(
                testee_id=f"testee_{i}", score=0.9 - i * 0.1, run_id=f"run_{i}",
                timestamp=now, num_tasks=5,
            ))
        
        top_3 = lb.get_top_n(3)
        assert len(top_3) == 3
        assert top_3[0].testee_id == "testee_0"
        assert top_3[1].testee_id == "testee_1"
        assert top_3[2].testee_id == "testee_2"


# ============================================================================
# LeaderboardCollection Tests
# ============================================================================


class TestLeaderboardCollection:
    """Tests for LeaderboardCollection model."""

    def test_collection_creation_empty(self):
        """Test creating empty collection."""
        collection = LeaderboardCollection()
        
        assert collection.leaderboards == {}
        assert collection.version == "1.0.0"
        assert isinstance(collection.created_at, datetime)

    def test_collection_add_leaderboard(self):
        """Test adding leaderboard to collection."""
        collection = LeaderboardCollection()
        
        lb = Leaderboard(
            leaderboard_id="overall_single_turn",
            name="Overall Single-Turn",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        collection.add_leaderboard(lb)
        
        assert "overall_single_turn" in collection.leaderboards
        assert collection.leaderboards["overall_single_turn"] == lb

    def test_collection_get_leaderboard(self):
        """Test getting leaderboard from collection."""
        collection = LeaderboardCollection()
        
        lb = Leaderboard(
            leaderboard_id="test_lb",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        
        collection.add_leaderboard(lb)
        
        retrieved = collection.get_leaderboard("test_lb")
        assert retrieved == lb
        
        missing = collection.get_leaderboard("nonexistent")
        assert missing is None

    def test_collection_list_leaderboard_ids(self):
        """Test listing all leaderboard IDs."""
        collection = LeaderboardCollection()
        
        for name in ["overall_single", "overall_multi", "completeness"]:
            lb = Leaderboard(
                leaderboard_id=name,
                name=name,
                description=name,
                evaluation_mode="single_turn",
                metric_name="overall",
            )
            collection.add_leaderboard(lb)
        
        ids = collection.list_leaderboard_ids()
        assert len(ids) == 3
        assert "overall_single" in ids
        assert "overall_multi" in ids
        assert "completeness" in ids

    def test_collection_add_entry(self):
        """Test adding entry to leaderboard via collection."""
        collection = LeaderboardCollection()
        
        lb = Leaderboard(
            leaderboard_id="test_lb",
            name="Test",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        collection.add_leaderboard(lb)
        
        entry = LeaderboardEntry(
            testee_id="dagent",
            score=0.85,
            run_id="run_123",
            timestamp=datetime.now(timezone.utc),
            num_tasks=10,
        )
        
        result = collection.add_entry("test_lb", entry)
        assert result is True
        
        retrieved_lb = collection.get_leaderboard("test_lb")
        assert len(retrieved_lb.entries) == 1
        assert retrieved_lb.entries[0].testee_id == "dagent"

    def test_collection_add_entry_missing_leaderboard(self):
        """Test adding entry to nonexistent leaderboard."""
        collection = LeaderboardCollection()
        
        entry = LeaderboardEntry(
            testee_id="dagent",
            score=0.85,
            run_id="run_123",
            timestamp=datetime.now(timezone.utc),
            num_tasks=10,
        )
        
        result = collection.add_entry("nonexistent", entry)
        assert result is False

    def test_collection_serialization_roundtrip(self):
        """Test JSON serialization/deserialization."""
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
            model_version="v1.0",
            score=0.85,
            run_id="run_123",
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
            num_tasks=10,
            breakdown={"completeness": 0.9, "robustness": 0.8},
        )
        lb.add_entry(entry)
        collection.add_leaderboard(lb)
        
        # Serialize
        json_str = collection.model_dump_json()
        
        # Deserialize
        restored = LeaderboardCollection.model_validate_json(json_str)
        
        # Verify
        assert restored.version == collection.version
        assert "test_lb" in restored.leaderboards
        
        restored_lb = restored.get_leaderboard("test_lb")
        assert restored_lb.name == "Test Leaderboard"
        assert len(restored_lb.entries) == 1
        assert restored_lb.entries[0].testee_id == "dagent"
        assert restored_lb.entries[0].breakdown["completeness"] == 0.9
