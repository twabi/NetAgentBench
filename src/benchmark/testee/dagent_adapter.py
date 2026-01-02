"""
Dagent adapter for multi-agent system integration.

Provides a testee adapter that connects to dagent's HTTP API,
enabling benchmark execution against multi-agent systems.

Note: This adapter is for internal research use. See WS2.3 in PHASE_2_IMPLEMENTATION.md.
"""
import logging
from typing import Dict, Any, Optional

from benchmark.testee.base import BaseTestee
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission
from benchmark.llm.presenter import LLMTaskPresenter
from benchmark.llm.parser import LLMResponseParser

logger = logging.getLogger(__name__)


class DagentAdapter(BaseTestee):
    """
    Dagent multi-agent system adapter.
    
    Connects to a dagent instance via HTTP and uses its multi-agent
    orchestration to generate network configuration submissions.
    
    From the benchmark's perspective, dagent is a single HTTP endpoint.
    All internal orchestration (DAG, FSM, multi-agent) is handled by dagent.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:8000",
        user_id: str = "benchmark",
        topic_type: Optional[str] = None,
        timeout: float = 300.0,
        testee_id: str = "dagent",
    ):
        """
        Initialize Dagent adapter.
        
        Args:
            endpoint: Dagent HTTP endpoint (default: localhost:8000)
            user_id: User ID for dagent conversations
            topic_type: Optional initial topic type for routing
            timeout: Request timeout in seconds (default: 300s for complex tasks)
            testee_id: Unique identifier for this testee
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx package is required for DagentAdapter. "
                "Install it with: pip install httpx"
            )
        
        self.endpoint = endpoint.rstrip("/")
        self.user_id = user_id
        self.topic_type = topic_type
        self.timeout = timeout
        self.testee_id = testee_id
        self.httpx = httpx
        
        # Reuse LLM components for task formatting and response parsing
        self.presenter = LLMTaskPresenter()
        self.parser = LLMResponseParser()
        
        # Tracking
        self.requests_made = 0
        self.conversation_id: Optional[str] = None

    def generate_submission(self, task: TaskDefinition) -> Submission:
        """
        Generate a configuration submission using dagent multi-agent system.
        
        Args:
            task: TaskDefinition specifying the network configuration problem
        
        Returns:
            Submission containing the dagent-generated configuration
        
        Raises:
            ConnectionError: If dagent is not reachable
            ValueError: If response cannot be parsed
        """
        logger.info(f"Generating submission for task {task.task_id} using dagent")
        
        # Format task as prompt using the same presenter as LLM testee
        prompt = self.presenter.format_task_for_llm(task)
        logger.debug(f"Prompt length: {len(prompt)} characters")
        
        # Send to dagent
        try:
            response_content = self._call_dagent(prompt, task)
            self.requests_made += 1
            
            logger.info(
                f"Received dagent response ({len(response_content)} characters) "
                f"for task {task.task_id}"
            )
            
        except Exception as e:
            logger.error(f"Dagent API call failed for task {task.task_id}: {e}")
            raise
        
        # Parse response into submission using same parser as LLM testee
        try:
            submission = self.parser.parse_response(
                response=response_content,
                task_id=task.task_id,
                testee_id=self.testee_id,
            )
            
            logger.info(
                f"Successfully parsed submission for task {task.task_id}: "
                f"{len(submission.approach.commands)} node configurations"
            )
            
            return submission
            
        except ValueError as e:
            logger.error(f"Failed to parse dagent response for task {task.task_id}: {e}")
            raise

    def _call_dagent(self, prompt: str, task: TaskDefinition) -> str:
        """
        Call dagent HTTP API.
        
        Args:
            prompt: Formatted task prompt
            task: Original task (passed as external metadata)
        
        Returns:
            Response content string from dagent
        """
        timeout_config = self.httpx.Timeout(
            connect=10.0,
            read=self.timeout,
            write=10.0,
            pool=10.0
        )
        
        url = f"{self.endpoint}/conversation/"
        logger.debug(f"DagentAdapter: Connecting to {url}")
        
        with self.httpx.Client(
            timeout=timeout_config,
            follow_redirects=True
        ) as client:
            try:
                # Build request body matching ConversationMessageDTO
                request_body = {
                    "user_id": self.user_id,
                    "content": prompt,
                    "external": {
                        "task_id": task.task_id,
                        "source": "benchmark",
                    }
                }
                
                # Add topic_type if specified
                if self.topic_type:
                    request_body["topic_type"] = self.topic_type
                
                # Add conversation_id for multi-turn if available
                if self.conversation_id:
                    request_body["conversation_id"] = self.conversation_id
                
                response = client.post(url, json=request_body)
                response.raise_for_status()
                json_response = response.json()
                
                # Extract response from dagent's Res wrapper
                # Structure: {"code": 0, "msg": "success", "data": {...}}
                if "data" in json_response:
                    data = json_response["data"]
                    
                    # Store conversation_id for potential multi-turn
                    if "conversation_id" in data:
                        self.conversation_id = str(data["conversation_id"])
                    
                    # Return content
                    content = data.get("content", "")
                    if not content:
                        logger.warning(
                            f"Dagent returned empty content. "
                            f"Response keys: {list(data.keys())}"
                        )
                    return content
                else:
                    # Fallback: check for direct content
                    logger.warning(
                        f"Unexpected dagent response structure: {list(json_response.keys())}"
                    )
                    return json_response.get("content", str(json_response))
                    
            except self.httpx.ConnectError as e:
                logger.error(f"Dagent connection error to {url}: {e}")
                raise ConnectionError(
                    f"Failed to connect to dagent at {self.endpoint}. "
                    f"Please verify the server is running: uvicorn dagent.main:app --reload"
                )
            except self.httpx.TimeoutException as e:
                logger.error(f"Dagent request timeout to {url}: {e}")
                raise TimeoutError(
                    f"Request to dagent at {self.endpoint} timed out after {self.timeout}s"
                )

    def get_testee_info(self) -> Dict[str, Any]:
        """
        Return metadata about this dagent testee.
        
        Returns:
            Dictionary with testee information
        """
        return {
            "testee_id": self.testee_id,
            "testee_type": "dagent",
            "framework": "dagent",
            "endpoint": self.endpoint,
            "user_id": self.user_id,
            "topic_type": self.topic_type,
            "requests_made": self.requests_made,
            "conversation_id": self.conversation_id,
        }

    def reset_conversation(self):
        """Reset conversation state for a new session."""
        self.conversation_id = None
        self.requests_made = 0
