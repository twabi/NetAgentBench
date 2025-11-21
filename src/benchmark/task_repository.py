"""
Task Repository for loading and managing benchmark tasks.

Provides functionality to load tasks organized by property type with
optional filtering and pagination.
"""
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from benchmark.models.task import TaskDefinition

logger = logging.getLogger(__name__)


class TaskRepository:
    """Load and manage benchmark tasks organized by property type."""

    VALID_PROPERTY_TYPES = ["reachability", "bgp_configuration", "ospf_configuration"]

    def __init__(self, tasks_dir: Path = Path("benchmark-tasks")):
        """
        Initialize TaskRepository.

        Args:
            tasks_dir: Path to the benchmark tasks directory

        Raises:
            FileNotFoundError: If index.json doesn't exist
        """
        self.tasks_dir = tasks_dir
        self.index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        """
        Load the task index file.

        Returns:
            Dictionary containing index metadata

        Raises:
            FileNotFoundError: If index.json doesn't exist
        """
        index_path = self.tasks_dir / "index.json"
        if not index_path.exists():
            raise FileNotFoundError(
                f"Task index not found: {index_path}. "
                "Run task generation script to create the index."
            )

        with open(index_path, 'r') as f:
            return json.load(f)

    def _load_tasks_from_dir(self, property_type: str) -> List[TaskDefinition]:
        """
        Load all tasks from a property type directory.

        Args:
            property_type: Property type to load tasks for

        Returns:
            List of TaskDefinition objects
        """
        tasks_path = self.tasks_dir / "property_types" / property_type / "tasks"

        if not tasks_path.exists():
            logger.warning(f"Tasks directory not found: {tasks_path}")
            return []

        tasks = []
        task_files = sorted(tasks_path.glob("*.json"))

        for task_file in task_files:
            try:
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                    task = TaskDefinition.model_validate(task_data)
                    tasks.append(task)
            except Exception as e:
                logger.warning(f"Failed to load task {task_file}: {e}")
                continue

        return tasks

    def load_tasks_by_property(
        self,
        property_type: str,
        limit: Optional[int] = None
    ) -> List[TaskDefinition]:
        """
        Load tasks for a specific property type.

        Args:
            property_type: "reachability", "bgp_configuration", "ospf_configuration"
            limit: Optional limit on number of tasks (None = all tasks)

        Returns:
            List of TaskDefinition objects

        Raises:
            ValueError: If property_type is invalid
        """
        if property_type not in self.VALID_PROPERTY_TYPES:
            raise ValueError(
                f"Invalid property type: {property_type}. "
                f"Valid types: {', '.join(self.VALID_PROPERTY_TYPES)}"
            )

        tasks = self._load_tasks_from_dir(property_type)

        # Apply limit if specified
        if limit is not None:
            tasks = tasks[:limit]

        return tasks

    def load_all_tasks(self, limit: Optional[int] = None) -> List[TaskDefinition]:
        """
        Load all tasks from all property types.

        Args:
            limit: Optional limit on total number of tasks (None = all tasks)

        Returns:
            List of TaskDefinition objects from all property types
        """
        all_tasks = []

        for property_type in self.VALID_PROPERTY_TYPES:
            property_tasks = self.load_tasks_by_property(property_type, limit=None)
            all_tasks.extend(property_tasks)

        # Apply global limit if specified
        if limit is not None:
            all_tasks = all_tasks[:limit]

        return all_tasks

    def get_property_count(self, property_type: str) -> int:
        """
        Get the count of tasks for a property type from the index.

        Args:
            property_type: Property type to get count for

        Returns:
            Number of tasks for the property type
        """
        if property_type not in self.VALID_PROPERTY_TYPES:
            raise ValueError(f"Invalid property type: {property_type}")

        return (
            self.index.get("property_types", {})
            .get(property_type, {})
            .get("count", 0)
        )

    def get_total_count(self) -> int:
        """
        Get the total number of tasks from the index.

        Returns:
            Total number of tasks
        """
        return self.index.get("total_tasks", 0)

    def load_task(self, task_id: str) -> TaskDefinition:
        """
        Load a single task by task ID.

        Args:
            task_id: Task identifier

        Returns:
            TaskDefinition object

        Raises:
            FileNotFoundError: If task is not found
        """
        # Search all property type directories for the task
        for property_type in self.VALID_PROPERTY_TYPES:
            tasks_path = self.tasks_dir / "property_types" / property_type / "tasks"
            task_file = tasks_path / f"{task_id}.json"

            if task_file.exists():
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                        return TaskDefinition.model_validate(task_data)
                except Exception as e:
                    raise FileNotFoundError(f"Failed to load task {task_id}: {e}")

        raise FileNotFoundError(f"Task not found: {task_id}")

    def list_tasks(self, property_type: Optional[str] = None) -> List[TaskDefinition]:
        """
        List tasks, optionally filtered by property type.

        Args:
            property_type: Optional property type to filter by

        Returns:
            List of TaskDefinition objects
        """
        if property_type:
            return self.load_tasks_by_property(property_type)
        else:
            return self.load_all_tasks()

