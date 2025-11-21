"""
Human testee implementations.

Supports humans participating in the benchmark via:
- JSON files: Pre-written configuration submissions
- Interactive CLI: Real-time configuration input (implemented separately)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from benchmark.testee.base import BaseTestee
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission

logger = logging.getLogger(__name__)


class HumanJsonTestee(BaseTestee):
    """
    Human testee that loads submissions from JSON files.
    
    Allows humans to participate in the benchmark by providing
    pre-written configuration submissions in JSON format.
    """

    def __init__(self, submission_file: str):
        """
        Initialize the human JSON testee.
        
        Args:
            submission_file: Path to JSON file containing the submission
        
        Raises:
            FileNotFoundError: If submission file doesn't exist
        """
        self.submission_file = Path(submission_file)
        self._submission_data: Optional[Dict[str, Any]] = None
        self._testee_id: Optional[str] = None
        self._testee_type: str = "human"

        # Validate file exists
        if not self.submission_file.exists():
            raise FileNotFoundError(
                f"Submission file not found: {submission_file}"
            )

    def generate_submission(self, task: TaskDefinition) -> Submission:
        """
        Load and return the submission from the JSON file.
        
        Args:
            task: TaskDefinition (used to validate task_id match)
        
        Returns:
            Submission loaded from the JSON file
        
        Raises:
            ValueError: If task_id in file doesn't match the task
            json.JSONDecodeError: If file is not valid JSON
        """
        # Load submission from file
        logger.info(f"Loading submission from {self.submission_file}")
        
        with open(self.submission_file, "r") as f:
            self._submission_data = json.load(f)

        # Parse into Submission object
        submission = Submission(**self._submission_data)

        # Validate task_id matches
        if submission.task_id != task.task_id:
            raise ValueError(
                f"Submission task_id mismatch: expected '{task.task_id}', "
                f"got '{submission.task_id}'"
            )

        # Store testee info for get_testee_info
        self._testee_id = submission.testee_id
        self._testee_type = submission.testee_type

        logger.info(
            f"Loaded submission for task {task.task_id} from {submission.testee_id}"
        )

        return submission

    def get_testee_info(self) -> Dict[str, Any]:
        """
        Return metadata about this human testee.
        
        Returns:
            Dictionary with testee information
        """
        return {
            "testee_id": self._testee_id or "unknown",
            "testee_type": self._testee_type,
            "description": f"Human testee (JSON file: {self.submission_file.name})",
            "submission_file": str(self.submission_file),
        }


class HumanInteractiveTestee(BaseTestee):
    """
    Interactive human testee for CLI usage.
    
    Prompts the user to provide submission file paths for each task
    during benchmark execution.
    """

    def __init__(self, testee_id: str = "human_interactive"):
        """
        Initialize the interactive human testee.
        
        Args:
            testee_id: Unique identifier for this testee
        """
        self.testee_id = testee_id
        self.testee_type = "human"
        self.submissions_provided = 0

    def generate_submission(self, task: TaskDefinition) -> Submission:
        """
        Prompt the user for a submission file for the given task.
        
        Args:
            task: TaskDefinition to generate submission for
        
        Returns:
            Submission loaded from user-provided file
        
        Raises:
            FileNotFoundError: If submission file doesn't exist
            ValueError: If submission validation fails
            KeyboardInterrupt: If user cancels
        """
        from benchmark.presenter import TaskPresenter
        
        # Display task to the user
        presenter = TaskPresenter()
        task_text = presenter.present_task_text(task)
        print(task_text)
        
        # Prompt for submission file
        while True:
            try:
                submission_path = input(f"Enter path to submission JSON for {task.task_id} (or 'skip' to skip): ").strip()
                
                if submission_path.lower() == 'skip':
                    logger.warning(f"User skipped task {task.task_id}")
                    raise ValueError(f"User skipped task {task.task_id}")
                
                # Load submission using HumanJsonTestee
                json_testee = HumanJsonTestee(submission_path)
                submission = json_testee.generate_submission(task)
                
                self.submissions_provided += 1
                logger.info(f"User provided submission for task {task.task_id}")
                
                return submission
                
            except FileNotFoundError as e:
                print(f"Error: {e}")
                print("Please provide a valid file path.")
            except ValueError as e:
                if "skipped" in str(e):
                    raise
                print(f"Error: {e}")
                print("Please provide a valid submission file.")
            except KeyboardInterrupt:
                print("\nBenchmark interrupted by user.")
                raise

    def get_testee_info(self) -> Dict[str, Any]:
        """
        Return metadata about this interactive human testee.
        
        Returns:
            Dictionary with testee information
        """
        return {
            "testee_id": self.testee_id,
            "testee_type": self.testee_type,
            "description": "Interactive human testee (CLI prompts)",
            "submissions_provided": self.submissions_provided,
        }

