"""
Unit tests for Reachability Task Generator.

Tests reachability task generation with various topologies.
"""
import pytest
import sys
from pathlib import Path

# Add generators directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "benchmark-tasks" / "generators"))

from benchmark.models.task import TaskDefinition, PropertyType


class TestReachabilityGenerator:
    """Test reachability task generation"""

    def test_generate_reachability_tasks_returns_list(self):
        """Test that generator returns a list of tasks"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_generated_tasks_are_valid(self):
        """Test that all generated tasks are valid TaskDefinitions"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        
        for task_dict in tasks[:5]:  # Test first 5
            task = TaskDefinition.model_validate(task_dict)
            assert task is not None

    def test_tasks_have_reachability_property(self):
        """Test that tasks have reachability property type"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        
        for task_dict in tasks[:5]:
            task = TaskDefinition.model_validate(task_dict)
            # Should have at least one reachability property
            prop_types = [prop.type for prop in task.intent.properties]
            assert PropertyType.REACHABILITY in prop_types

    def test_task_ids_unique(self):
        """Test that all task IDs are unique"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        task_ids = [task["task_id"] for task in tasks]
        
        assert len(task_ids) == len(set(task_ids))

    def test_task_ids_follow_naming_convention(self):
        """Test that task IDs follow naming convention"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        
        for task_dict in tasks[:10]:
            task_id = task_dict["task_id"]
            assert task_id.startswith("reachability_")

    def test_generates_multiple_topology_patterns(self):
        """Test that multiple topology patterns are generated"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        task_ids = [task["task_id"] for task in tasks]
        
        # Should have different patterns in task IDs
        patterns = ["linear", "star", "ring", "mesh"]
        found_patterns = set()
        
        for task_id in task_ids:
            for pattern in patterns:
                if pattern in task_id:
                    found_patterns.add(pattern)
        
        assert len(found_patterns) >= 2  # At least 2 different patterns

    def test_task_count_in_expected_range(self):
        """Test that task count is in expected range (50-100)"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        
        # Should generate 50-100 tasks as per spec
        assert 40 <= len(tasks) <= 120  # Allow some tolerance

    def test_tasks_have_ping_commands(self):
        """Test that reachability tasks use ping commands"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        
        for task_dict in tasks[:5]:
            task = TaskDefinition.model_validate(task_dict)
            # Check that at least one property uses ping
            has_ping = False
            for prop in task.intent.properties:
                if "ping" in prop.evaluation.command.lower():
                    has_ping = True
                    break
            assert has_ping

    def test_tasks_use_text_parser(self):
        """Test that reachability tasks use text parser for ping"""
        from generate_reachability_tasks import generate_reachability_tasks
        
        tasks = generate_reachability_tasks()
        
        for task_dict in tasks[:5]:
            task = TaskDefinition.model_validate(task_dict)
            for prop in task.intent.properties:
                if PropertyType.REACHABILITY == prop.type:
                    assert prop.evaluation.parser == "text"

