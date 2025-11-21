"""
Unit tests for Task Repository.

Tests repository functionality for loading and filtering tasks by property type.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from typing import List

from benchmark.models.task import TaskDefinition


class TestTaskRepositoryInitialization:
    """Test TaskRepository initialization"""

    def test_repository_initializes_with_default_path(self):
        """Test that TaskRepository can be initialized with default path"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository()
                assert repo.tasks_dir == Path("benchmark-tasks")

    def test_repository_initializes_with_custom_path(self):
        """Test that TaskRepository can be initialized with custom path"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        custom_path = Path("/custom/path")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=custom_path)
                assert repo.tasks_dir == custom_path

    def test_repository_loads_index_on_init(self):
        """Test that repository loads index.json on initialization"""
        from benchmark.task_repository import TaskRepository
        
        # Mock the index file
        mock_index = {
            "version": "1.0",
            "total_tasks": 10,
            "property_types": {
                "reachability": {"count": 5},
                "bgp_configuration": {"count": 3},
                "ospf_configuration": {"count": 2}
            }
        }
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
                assert repo.index is not None
                assert repo.index["total_tasks"] == 10


class TestTaskRepositoryLoadByProperty:
    """Test loading tasks by property type"""

    def test_load_tasks_by_property_returns_list(self):
        """Test that load_tasks_by_property returns a list of TaskDefinitions"""
        from benchmark.task_repository import TaskRepository
        
        # Mock the index loading
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        with patch.object(repo, "_load_tasks_from_dir") as mock_load:
            mock_load.return_value = []
            tasks = repo.load_tasks_by_property("reachability")
            assert isinstance(tasks, list)

    def test_load_tasks_by_property_with_limit(self):
        """Test that limit parameter works correctly"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        # Mock 10 tasks
        mock_tasks = [Mock(spec=TaskDefinition) for _ in range(10)]
        
        with patch.object(repo, "_load_tasks_from_dir") as mock_load:
            mock_load.return_value = mock_tasks
            tasks = repo.load_tasks_by_property("reachability", limit=5)
            assert len(tasks) == 5

    def test_load_tasks_by_property_no_limit(self):
        """Test that None limit returns all tasks"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        mock_tasks = [Mock(spec=TaskDefinition) for _ in range(10)]
        
        with patch.object(repo, "_load_tasks_from_dir") as mock_load:
            mock_load.return_value = mock_tasks
            tasks = repo.load_tasks_by_property("reachability", limit=None)
            assert len(tasks) == 10

    def test_load_tasks_validates_property_type(self):
        """Test that invalid property type raises error"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        with pytest.raises(ValueError, match="Invalid property type"):
            repo.load_tasks_by_property("invalid_property")


class TestTaskRepositoryLoadAll:
    """Test loading all tasks"""

    def test_load_all_tasks_returns_list(self):
        """Test that load_all_tasks returns a list of TaskDefinitions"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        with patch.object(repo, "load_tasks_by_property") as mock_load:
            mock_load.return_value = []
            tasks = repo.load_all_tasks()
            assert isinstance(tasks, list)

    def test_load_all_tasks_aggregates_all_properties(self):
        """Test that load_all_tasks loads from all property types"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        # Mock different number of tasks per property
        def mock_load_by_property(prop_type, limit=None):
            counts = {
                "reachability": 5,
                "bgp_configuration": 3,
                "ospf_configuration": 2
            }
            return [Mock(spec=TaskDefinition) for _ in range(counts.get(prop_type, 0))]
        
        with patch.object(repo, "load_tasks_by_property", side_effect=mock_load_by_property):
            tasks = repo.load_all_tasks()
            assert len(tasks) == 10  # 5 + 3 + 2

    def test_load_all_tasks_with_limit(self):
        """Test that global limit works across all properties"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {"version": "1.0", "total_tasks": 0}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        # Mock 20 total tasks
        def mock_load_by_property(prop_type, limit=None):
            return [Mock(spec=TaskDefinition) for _ in range(7)]
        
        with patch.object(repo, "load_tasks_by_property", side_effect=mock_load_by_property):
            tasks = repo.load_all_tasks(limit=10)
            assert len(tasks) == 10


class TestTaskRepositoryErrorHandling:
    """Test error handling in TaskRepository"""

    def test_missing_index_file_raises_error(self):
        """Test that missing index.json raises appropriate error"""
        from benchmark.task_repository import TaskRepository
        
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="index.json"):
                TaskRepository(tasks_dir=Path("nonexistent"))

    def test_missing_property_directory_returns_empty(self):
        """Test that missing property directory returns empty list"""
        from benchmark.task_repository import TaskRepository
        
        mock_index = {
            "version": "1.0",
            "total_tasks": 0,
            "property_types": {}
        }
        
        # Mock index exists
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_index))):
                repo = TaskRepository(tasks_dir=Path("test-tasks"))
        
        # Now mock property directory doesn't exist
        with patch.object(Path, "exists", return_value=False):
            tasks = repo.load_tasks_by_property("reachability")
            assert tasks == []

    def test_invalid_task_file_skipped(self):
        """Test that invalid task files are skipped with warning"""
        from benchmark.task_repository import TaskRepository
        
        # This will be tested once we implement the actual loading logic
        pass

