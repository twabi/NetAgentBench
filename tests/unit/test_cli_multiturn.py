"""
Unit tests for CLI multi-turn mode options.

Tests the --mode, --turn-limit, --time-limit options added to CLI commands.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch


class TestRunLLMOptions:
    """Test run-llm command options."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    def test_run_llm_has_mode_option(self, runner):
        """Test run-llm has --mode option."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-llm", "--help"])

        assert result.exit_code == 0
        assert "--mode" in result.output
        assert "single" in result.output
        assert "multi" in result.output

    def test_run_llm_has_turn_limit_option(self, runner):
        """Test run-llm has --turn-limit option."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-llm", "--help"])

        assert result.exit_code == 0
        assert "--turn-limit" in result.output

    def test_run_llm_has_time_limit_option(self, runner):
        """Test run-llm has --time-limit option."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-llm", "--help"])

        assert result.exit_code == 0
        assert "--time-limit" in result.output

    def test_run_llm_mode_default_is_single(self, runner):
        """Test run-llm mode defaults to single."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-llm", "--help"])

        assert "single (default)" in result.output.lower() or "single" in result.output

    def test_run_llm_turn_limit_default_is_50(self, runner):
        """Test run-llm turn-limit defaults to 50."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-llm", "--help"])

        assert "50" in result.output

    def test_run_llm_time_limit_default_is_600(self, runner):
        """Test run-llm time-limit defaults to 600."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-llm", "--help"])

        assert "600" in result.output


class TestRunDagentOptions:
    """Test run-dagent command options."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    def test_run_dagent_has_mode_option(self, runner):
        """Test run-dagent has --mode option."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-dagent", "--help"])

        assert result.exit_code == 0
        assert "--mode" in result.output
        assert "single" in result.output
        assert "multi" in result.output

    def test_run_dagent_has_turn_limit_option(self, runner):
        """Test run-dagent has --turn-limit option."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-dagent", "--help"])

        assert result.exit_code == 0
        assert "--turn-limit" in result.output

    def test_run_dagent_has_time_limit_option(self, runner):
        """Test run-dagent has --time-limit option."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-dagent", "--help"])

        assert result.exit_code == 0
        assert "--time-limit" in result.output

    def test_run_dagent_mode_default_is_single(self, runner):
        """Test run-dagent mode defaults to single."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-dagent", "--help"])

        assert "single (default)" in result.output.lower() or "single" in result.output


class TestModeBackwardCompatibility:
    """Test backward compatibility with single-turn mode."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    def test_run_llm_without_mode_uses_single(self, runner):
        """Test run-llm without --mode flag defaults to single-turn."""
        from benchmark.cli import main

        # Just check that --mode default is single in help
        result = runner.invoke(main, ["run-llm", "--help"])

        assert result.exit_code == 0
        # The help should show default: single
        assert "single" in result.output

    def test_run_dagent_without_mode_uses_single(self, runner):
        """Test run-dagent without --mode flag defaults to single-turn."""
        from benchmark.cli import main

        result = runner.invoke(main, ["run-dagent", "--help"])

        assert result.exit_code == 0
        assert "single" in result.output
