"""
Integration tests for task library.

Tests end-to-end workflow of task generation, loading, and repository functionality.
"""
import pytest
from pathlib import Path

from benchmark.task_repository import TaskRepository
from benchmark.models.task import TaskDefinition, PropertyType


class TestTaskLibraryIntegration:
    """Integration tests for complete task library workflow"""

    @pytest.fixture
    def task_repo(self) -> TaskRepository:
        """Create TaskRepository pointing to generated tasks"""
        tasks_dir = Path(__file__).parent.parent.parent / "benchmark-tasks"
        return TaskRepository(tasks_dir=tasks_dir)

    def test_repository_loads_index(self, task_repo: TaskRepository):
        """Test that repository successfully loads task index"""
        assert task_repo.index is not None
        assert "total_tasks" in task_repo.index
        assert "property_types" in task_repo.index

    def test_repository_reports_correct_counts(self, task_repo: TaskRepository):
        """Test that repository reports correct task counts from index"""
        total = task_repo.get_total_count()
        assert total > 0
        assert total == 121  # Expected from generation

    def test_load_reachability_tasks(self, task_repo: TaskRepository):
        """Test loading reachability tasks"""
        tasks = task_repo.load_tasks_by_property("reachability")
        
        assert len(tasks) > 0
        assert all(isinstance(task, TaskDefinition) for task in tasks)
        
        # Verify all tasks have reachability properties
        for task in tasks[:5]:  # Check first 5
            prop_types = [prop.type for prop in task.intent.properties]
            assert PropertyType.REACHABILITY in prop_types

    def test_load_bgp_tasks(self, task_repo: TaskRepository):
        """Test loading BGP configuration tasks"""
        tasks = task_repo.load_tasks_by_property("bgp_configuration")
        
        assert len(tasks) > 0
        assert all(isinstance(task, TaskDefinition) for task in tasks)
        
        # Verify all tasks have BGP properties
        for task in tasks[:5]:
            prop_types = [prop.type for prop in task.intent.properties]
            assert PropertyType.BGP_CONFIGURATION in prop_types

    def test_load_ospf_tasks(self, task_repo: TaskRepository):
        """Test loading OSPF configuration tasks"""
        tasks = task_repo.load_tasks_by_property("ospf_configuration")
        
        assert len(tasks) > 0
        assert all(isinstance(task, TaskDefinition) for task in tasks)
        
        # Verify all tasks have OSPF properties
        for task in tasks[:5]:
            prop_types = [prop.type for prop in task.intent.properties]
            assert PropertyType.OSPF_CONFIGURATION in prop_types

    def test_load_tasks_with_limit(self, task_repo: TaskRepository):
        """Test loading tasks with limit parameter"""
        tasks = task_repo.load_tasks_by_property("reachability", limit=10)
        
        assert len(tasks) == 10
        assert all(isinstance(task, TaskDefinition) for task in tasks)

    def test_load_all_tasks(self, task_repo: TaskRepository):
        """Test loading all tasks across property types"""
        all_tasks = task_repo.load_all_tasks()
        
        assert len(all_tasks) > 0
        assert len(all_tasks) == 121  # Expected total
        assert all(isinstance(task, TaskDefinition) for task in all_tasks)

    def test_load_all_tasks_with_limit(self, task_repo: TaskRepository):
        """Test loading all tasks with global limit"""
        limited_tasks = task_repo.load_all_tasks(limit=50)
        
        assert len(limited_tasks) == 50
        assert all(isinstance(task, TaskDefinition) for task in limited_tasks)

    def test_tasks_have_unique_ids(self, task_repo: TaskRepository):
        """Test that all task IDs are unique"""
        all_tasks = task_repo.load_all_tasks()
        task_ids = [task.task_id for task in all_tasks]
        
        assert len(task_ids) == len(set(task_ids)), "Task IDs are not unique"

    def test_tasks_have_valid_topologies(self, task_repo: TaskRepository):
        """Test that all tasks have valid topologies"""
        all_tasks = task_repo.load_all_tasks(limit=20)
        
        for task in all_tasks:
            assert len(task.topology.nodes) > 0, f"Task {task.task_id} has no nodes"
            assert len(task.intent.properties) > 0, f"Task {task.task_id} has no properties"

    def test_property_type_distribution(self, task_repo: TaskRepository):
        """Test that tasks are distributed across property types"""
        all_tasks = task_repo.load_all_tasks()
        
        property_type_counts = {}
        for task in all_tasks:
            for prop in task.intent.properties:
                prop_type = prop.type
                property_type_counts[prop_type] = property_type_counts.get(prop_type, 0) + 1
        
        # Should have all three property types
        assert PropertyType.REACHABILITY in property_type_counts
        assert PropertyType.BGP_CONFIGURATION in property_type_counts
        assert PropertyType.OSPF_CONFIGURATION in property_type_counts

