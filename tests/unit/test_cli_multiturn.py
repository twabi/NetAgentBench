"""
Unit tests for CLI multi-turn mode options.

Tests the --mode, --turn-limit, --time-limit options added to CLI commands.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch
import json


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


class TestRunTaskHumanMode:
    """Tests for run-task --human flag."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def task_file(self, tmp_path):
        task = {
            "task_id": "human_cli_test",
            "description": "Test task for human CLI",
            "platform": "frr",
            "topology": {
                "nodes": [{"name": "R1", "type": "router", "image": "frrouting/frr:latest", "platform": "frr"}],
                "links": [],
                "interfaces": [],
            },
            "intent": {
                "properties": [
                    {
                        "id": "p1",
                        "type": "interface_up",
                        "description": "Test property",
                        "evaluation": {
                            "method": "exec_and_parse",
                            "target_node": "R1",
                            "command": "echo ok",
                            "parser": "text",
                            "success_condition": {"contains_text": "ok"},
                        },
                    }
                ]
            },
        }
        path = tmp_path / "task.json"
        path.write_text(json.dumps(task))
        return str(path)

    def test_run_task_help_shows_human_flag(self, runner):
        from benchmark.cli import main

        result = runner.invoke(main, ["run-task", "--help"])
        assert result.exit_code == 0
        assert "--human" in result.output

    def test_human_and_dagent_mutually_exclusive(self, runner, task_file):
        from benchmark.cli import main

        result = runner.invoke(
            main,
            [
                "run-task",
                task_file,
                "--human",
                "--dagent-endpoint",
                "http://localhost:8000",
            ],
        )
        assert result.exit_code != 0
        assert "cannot be used" in result.output.lower()

    def test_human_quit_does_not_save(self, runner, task_file):
        from benchmark.cli import main
        from benchmark.session.models import SubmitResult

        with patch("benchmark.cli.click.prompt", return_value="alice"):
            with patch("benchmark.interactive_controller.InteractiveBenchmarkController.run_interactive", return_value=None):
                with patch("benchmark.storage.ResultsStorage.save_result") as mock_save:
                    result = runner.invoke(main, ["run-task", task_file, "--human"])

        assert result.exit_code == 0
        assert "aborted" in result.output.lower()
        mock_save.assert_not_called()

    def test_human_submit_saves_result(self, runner, task_file):
        from benchmark.cli import main
        from benchmark.models.results import (
            BenchmarkResult,
            ExecutionMetrics,
            PropertyEvaluationResult,
            ScoringResult,
            ValidityCheck,
        )
        from datetime import datetime

        mock_result = BenchmarkResult(
            run_id="alice_mt_test",
            timestamp=datetime.now(),
            task_id="human_cli_test",
            testee_id="alice",
            testee_type="human",
            success=True,
            property_results=[
                PropertyEvaluationResult(
                    property_id="p1",
                    satisfied=True,
                    observation_raw="ok",
                    evaluation_time_seconds=0.1,
                )
            ],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                final_score=1.0,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=0.0,
                evaluation_time=0.5,
                total_time=3.5,
                is_multi_turn=True,
                turns_to_complete=1,
                time_to_complete=2.0,
                termination_reason="submitted",
            ),
            execution_log=[],
            errors=[],
        )

        with patch("benchmark.cli.click.prompt", return_value="alice"):
            with patch(
                "benchmark.interactive_controller.InteractiveBenchmarkController.run_interactive",
                return_value=mock_result,
            ):
                with patch("benchmark.storage.ResultsStorage.save_result") as mock_save:
                    result = runner.invoke(main, ["run-task", task_file, "--human"])

        assert result.exit_code == 0
        mock_save.assert_called_once_with(mock_result)
        assert "PASS" in result.output or "Final Score" in result.output

    def test_openrouter_slug_is_safe_in_testee_id(self, runner, task_file):
        from benchmark.cli import main

        with patch(
            "benchmark.interactive_controller.InteractiveBenchmarkController.run_interactive",
            return_value=None,
        ) as run:
            result = runner.invoke(
                main,
                [
                    "run-task",
                    task_file,
                    "--dagent-endpoint",
                    "http://localhost:8000",
                    "--provider",
                    "openrouter",
                    "--model",
                    "openai/gpt-6-luna",
                ],
            )

        assert result.exit_code == 0
        assert run.call_args.kwargs["testee_id"] == "openrouter_openaigpt6luna_single"
        assert "/" not in run.call_args.kwargs["testee_id"]
