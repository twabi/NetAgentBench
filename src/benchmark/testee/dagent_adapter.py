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
        provider: str = "openai",
        model: Optional[str] = None,
        agent_mode: str = "single",
        structure: str = "sequential",
        timeout: float = 300.0,
        testee_id: str = "dagent",
    ):
        """
        Initialize Dagent adapter.
        
        Args:
            endpoint: Dagent HTTP endpoint (default: localhost:8000)
            provider: LLM provider (openai, anthropic, etc.)
            model: Model name
            agent_mode: Agent mode ("single" or "multi")
            structure: Multi-agent structure ("sequential", "concurrent", "debate", "group_chat")
            timeout: Request timeout in seconds
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
        self.provider = provider
        self.model = model
        self.agent_mode = agent_mode
        self.structure = structure
        self.timeout = timeout
        self.testee_id = testee_id
        self.httpx = httpx
        
        # Tracking
        self.requests_made = 0

    def generate_submission(self, task: TaskDefinition) -> Submission:
        """
        Generate a configuration submission using dagent one-shot API.
        """
        logger.info(f"Generating submission for task {task.task_id} using dagent")
        
        try:
            response_data = self._call_dagent_generate(task)
            self.requests_made += 1
            
            # Convert response actions to Submission
            actions = response_data.get("actions", [])
            
            # Group commands by node
            from collections import defaultdict
            node_commands = defaultdict(list)
            
            for action in actions:
                if action.get("action") == "exec_command":
                    node_input = action.get("input", {})
                    # Handle both structure formats just in case
                    node = node_input.get("node")
                    cmd = node_input.get("command")
                    
                    if node and cmd:
                        node_commands[node].append(cmd)
            
            # Create CommandSequence objects
            submission_commands = []
            for node, cmds in node_commands.items():
                submission_commands.append({
                    "node": node,
                    "commands": cmds
                })
            
            logger.info(
                f"Received dagent response: {len(actions)} actions -> "
                f"{len(submission_commands)} node sequences "
                f"for task {task.task_id}"
            )
            
            # Create Submission object
            from benchmark.models.submission import Submission, Approach
            
            return Submission(
                task_id=task.task_id,
                testee_id=self.testee_id,
                testee_type="dagent",
                approach=Approach(commands=submission_commands),
                model_info={
                    "provider": self.provider,
                    "model": response_data.get("model_version", "unknown")
                }
            )
            
        except Exception as e:
            logger.error(f"Dagent API call failed for task {task.task_id}: {e}")
            raise

    def _call_dagent_generate(self, task: TaskDefinition) -> Dict[str, Any]:
        """Call dagent /benchmark/generate endpoint."""
        timeout_config = self.httpx.Timeout(
            connect=10.0, read=self.timeout, write=10.0, pool=10.0
        )
        
        url = f"{self.endpoint}/benchmark/generate"
        logger.debug(f"DagentAdapter: Connecting to {url}")
        
        # Prepare request payload matching GenerateTaskRequest
        # Include topology links so LLM knows interface connections
        payload = {
            "task_id": task.task_id,
            "description": task.description,
            "nodes": [n.name for n in task.topology.nodes],
            "links": [
                {"endpoints": link.endpoints}
                for link in task.topology.links
            ],
            "platform": task.platform if hasattr(task, "platform") else "frr",
            "properties": [
                {
                    "id": p.id,
                    "type": p.type.value if hasattr(p.type, "value") else str(p.type),
                    "description": p.description,
                    "evaluation": p.evaluation.model_dump() if hasattr(p.evaluation, "model_dump") else p.evaluation.dict()
                }
                for p in task.intent.properties
            ],
            "provider": self.provider,
            "model": self.model,
            "agent_mode": self.agent_mode,
            "structure": self.structure,
        }
        
        with self.httpx.Client(timeout=timeout_config) as client:
            try:
                response = client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
                
            except self.httpx.ConnectError:
                raise ConnectionError(
                    f"Failed to connect to dagent at {self.endpoint}. "
                    "Make sure it is running."
                )
            except self.httpx.TimeoutException:
                raise TimeoutError(
                    f"Request to dagent timed out after {self.timeout}s"
                )

    def get_testee_info(self) -> Dict[str, Any]:
        """Return metadata."""
        return {
            "testee_id": self.testee_id,
            "testee_type": "dagent",
            "endpoint": self.endpoint,
            "provider": self.provider,
            "model": self.model,
            "requests_made": self.requests_made,
        }

