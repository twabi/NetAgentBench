"""
Unit tests for leaderboard CLI commands.

Tests the leaderboard command group in cli.py.
"""
import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from click.testing import CliRunner

from benchmark.cli import main
from benchmark.storage import ResultsStorage
from benchmark.models.leaderboard import (
    LeaderboardEntry,
    Leaderboard,
    LeaderboardCollection,
)


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage for testing."""
    return ResultsStorage(base_dir=str(tmp_path))


class TestLeaderboardInit:
    """Tests for 'benchmark leaderboard init' command."""

    def test_init_creates_leaderboards(self, cli_runner, tmp_path):
        """Test that init creates standard leaderboards."""
        result = cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 0
        assert "Initialized 14 standard leaderboards" in result.output
        
        # Verify file created
        leaderboards_path = tmp_path / "leaderboards.json"
        assert leaderboards_path.exists()

    def test_init_existing_leaderboards_no_overwrite(self, cli_runner, tmp_path):
        """Test that init doesn't overwrite existing leaderboards."""
        # First init
        cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        # Second init
        result = cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 0
        assert "already exist" in result.output


class TestLeaderboardList:
    """Tests for 'benchmark leaderboard list' command."""

    def test_list_empty(self, cli_runner, tmp_path):
        """Test listing when no leaderboards exist."""
        result = cli_runner.invoke(main, [
            "leaderboard", "list", "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 0
        assert "No leaderboards found" in result.output

    def test_list_after_init(self, cli_runner, tmp_path):
        """Test listing after initialization."""
        # Init
        cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        # List
        result = cli_runner.invoke(main, [
            "leaderboard", "list", "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 0
        assert "Available leaderboards (14)" in result.output
        assert "overall_single_turn" in result.output
        assert "overall_multi_turn" in result.output


class TestLeaderboardShow:
    """Tests for 'benchmark leaderboard show' command."""

    def test_show_not_found(self, cli_runner, tmp_path):
        """Test showing nonexistent leaderboard."""
        # Init first
        cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        result = cli_runner.invoke(main, [
            "leaderboard", "show", "nonexistent", "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 1
        assert "Leaderboard not found" in result.output

    def test_show_empty_leaderboard(self, cli_runner, tmp_path):
        """Test showing leaderboard with no entries."""
        # Init first
        cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        result = cli_runner.invoke(main, [
            "leaderboard", "show", "overall_single_turn", "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 0
        assert "Overall (Single-Turn)" in result.output
        assert "No entries yet" in result.output

    def test_show_with_entries(self, cli_runner, tmp_path):
        """Test showing leaderboard with entries."""
        storage = ResultsStorage(base_dir=str(tmp_path))
        
        # Create leaderboard with entries
        collection = LeaderboardCollection()
        lb = Leaderboard(
            leaderboard_id="overall_single_turn",
            name="Overall (Single-Turn)",
            description="Test",
            evaluation_mode="single_turn",
            metric_name="overall",
        )
        for testee, score in [("dagent", 0.90), ("gpt-4o", 0.85)]:
            entry = LeaderboardEntry(
                testee_id=testee,
                score=score,
                run_id=f"run_{testee}",
                timestamp=datetime.now(timezone.utc),
                num_tasks=10,
            )
            lb.add_entry(entry)
        collection.add_leaderboard(lb)
        storage.save_leaderboards(collection)
        
        result = cli_runner.invoke(main, [
            "leaderboard", "show", "overall_single_turn", "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 0
        assert "dagent" in result.output
        assert "gpt-4o" in result.output
        assert "0.900" in result.output


class TestLeaderboardExport:
    """Tests for 'benchmark leaderboard export' command."""

    def test_export_no_leaderboards(self, cli_runner, tmp_path):
        """Test export when no leaderboards exist."""
        export_path = tmp_path / "export.json"
        
        result = cli_runner.invoke(main, [
            "leaderboard", "export", "--output", str(export_path),
            "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 1
        assert "No leaderboards found" in result.output

    def test_export_success(self, cli_runner, tmp_path):
        """Test successful export."""
        # Init first
        cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        export_path = tmp_path / "export.json"
        result = cli_runner.invoke(main, [
            "leaderboard", "export", "--output", str(export_path),
            "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 0
        assert "Exported 14 leaderboards" in result.output
        assert export_path.exists()
        
        # Verify content
        with open(export_path) as f:
            data = json.load(f)
        
        assert "leaderboards" in data
        assert len(data["leaderboards"]) == 14


class TestLeaderboardUpdate:
    """Tests for 'benchmark leaderboard update' command."""

    def test_update_no_leaderboards(self, cli_runner, tmp_path):
        """Test update when no leaderboards exist."""
        result = cli_runner.invoke(main, [
            "leaderboard", "update", "--run-id", "run_123",
            "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 1
        assert "No leaderboards found" in result.output

    def test_update_run_not_found(self, cli_runner, tmp_path):
        """Test update when run doesn't exist."""
        # Init first
        cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        result = cli_runner.invoke(main, [
            "leaderboard", "update", "--run-id", "nonexistent_run",
            "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 1
        assert "Benchmark run not found" in result.output


class TestLeaderboardUpdateTestee:
    """Tests for 'benchmark leaderboard update-testee' command."""

    def test_update_testee_no_leaderboards(self, cli_runner, tmp_path):
        """Test update-testee when no leaderboards exist."""
        result = cli_runner.invoke(main, [
            "leaderboard", "update-testee", "--testee-id", "dagent",
            "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 1
        assert "No leaderboards found" in result.output

    def test_update_testee_no_runs(self, cli_runner, tmp_path):
        """Test update-testee when testee has no runs."""
        # Init first
        cli_runner.invoke(main, [
            "leaderboard", "init", "--output-dir", str(tmp_path)
        ])
        
        result = cli_runner.invoke(main, [
            "leaderboard", "update-testee", "--testee-id", "nonexistent_testee",
            "--output-dir", str(tmp_path)
        ])
        
        assert result.exit_code == 1
        assert "No benchmark runs found" in result.output
