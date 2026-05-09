"""
Concurrent Pattern for Multi-Agent System.

Implements a fan-out/aggregate pattern where:
1. Task is split into subtasks
2. Multiple agents process subtasks concurrently
3. Results are aggregated into final output
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from autogen_core import SingleThreadedAgentRuntime
from autogen_core.models import (
    ChatCompletionClient,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    LLMMessage,
)

from dagent.core.agent.patterns.base import BasePattern
from dagent.core.agent.conversation.manager import Conversation

logger = logging.getLogger(__name__)


SPLITTER_PROMPT = """You are a TASK SPLITTER. Split the task into INDEPENDENT subtasks for parallel execution.

IMPORTANT: Output ONLY valid JSON with this EXACT structure:
{
    "subtasks": [
        {"id": "1", "description": "Configure IP addresses on R1"},
        {"id": "2", "description": "Configure IP addresses on R2"},
        {"id": "3", "description": "Configure routing on all routers"},
        {"id": "4", "description": "Verify connectivity"}
    ]
}

Rules:
- Split by ROUTER or by INDEPENDENT configuration steps
- Each subtask must be executable without waiting for others
- Keep subtasks SIMPLE and ACTIONABLE
- 3-6 subtasks is ideal
- DO NOT include the full task description in subtasks
- DO NOT return anything except the JSON object above
"""

WORKER_PROMPT = """You are a WORKER AGENT.
Your goal is to complete the assigned subtask using the available tools.

Use the ReAct pattern:
1. THOUGHT: Analyze what needs to be done
2. ACTION: Call a tool to make progress
3. OBSERVATION: Review the result

Respond in JSON format:
{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": {...}
}

When your subtask is complete, respond with:
{
    "thought": "Subtask complete",
    "action": "subtask_complete",
    "action_input": {"result": "summary of what was done"}
}
"""

AGGREGATOR_PROMPT = """You are an AGGREGATOR AGENT.
Your goal is to combine the results from multiple workers into a final result.

Review the results from each worker.
Determine if all subtasks were completed successfully.
If successful, submit the final result.

Respond in JSON format:
{
    "analysis": "Review of all subtask results",
    "all_successful": true or false,
    "action": "submit" or "report_issues",
    "summary": "Final summary of the combined work"
}
"""


class ConcurrentPattern(BasePattern):
    """
    Concurrent multi-agent pattern: Split → Process concurrently → Aggregate.
    
    This pattern:
    1. Splits the task into independent subtasks
    2. Runs workers on subtasks concurrently (simulated via sequential for simplicity)
    3. Aggregates results and submits
    
    Note: True parallelism requires async task management; this implementation
    uses sequential execution with the concurrent pattern structure.
    """
    
    def __init__(
        self,
        runtime: SingleThreadedAgentRuntime,
        config: Any,
        model_client: ChatCompletionClient,
        tool_executor: Any = None,
        system_prompt: str = None,
        max_workers: int = 3,
        max_retries: int = 3,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize concurrent pattern.
        
        Args:
            runtime: AutoGen Core runtime
            config: MAS configuration
            model_client: LLM client for all agents
            tool_executor: Object providing tool execution methods
            system_prompt: System prompt containing tool info
            max_workers: Maximum concurrent workers (for future true parallelism)
            max_retries: Max retries for parsing errors
            logger: Optional logger instance
        """
        super().__init__(runtime, config, logger)
        self._model_client = model_client
        self._tool_executor = tool_executor
        self._system_prompt = system_prompt or ""
        self._max_workers = max_workers
        self._max_retries = max_retries
        
        # Execution state
        self._actions_executed: List[Dict[str, Any]] = []
        self._reasoning_trace: List[Dict[str, Any]] = []
        
        # Token and tool tracking
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._tool_calls: Dict[str, int] = {}
    
    async def register_agents(self) -> None:
        """Register agents for concurrent pattern."""
        self._logger.debug("ConcurrentPattern: No explicit agent registration needed")
    
    @property
    def entry_topic(self) -> str:
        return "concurrent"
    
    async def execute(
        self,
        task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """
        Execute concurrent pattern on the task.
        """
        self._actions_executed = []
        self._reasoning_trace = []
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_tokens = 0
        self._tool_calls = {}
        
        task_id = task.get("task_id", "unknown")
        time_limit = task.get("time_limit", 600.0)
        self._logger.info(f"Starting ConcurrentPattern on task: {task_id}")
        
        import time as time_pkg
        start_time = time_pkg.time()
        
        total_turns = 0
        
        # 1. SPLITTER PHASE: Split task into subtasks
        self._logger.info("--- Phase 1: Splitter ---")
        subtasks = await self._run_splitter(task)
        total_turns += 1
        
        if not subtasks:
            return self._make_result(
                success=False,
                turns_used=total_turns,
                error="Splitter failed to generate subtasks",
            )
        
        self._log_reasoning("subtasks", json.dumps(subtasks, indent=2))
        
        # 2. WORKER PHASE: Process subtasks concurrently
        self._logger.info(f"--- Phase 2: Workers ({len(subtasks)} subtasks) ---")
        worker_results = []
        
        # Execute workers (using asyncio.gather for concurrent execution)
        worker_tasks = [
            self._run_worker(subtask, task, conversation, start_time=start_time, time_limit=time_limit)
            for subtask in subtasks
        ]
        worker_results = await asyncio.gather(*worker_tasks)
        
        for result in worker_results:
            total_turns += result.get("turns", 0)
        
        # 3. AGGREGATOR PHASE: Combine results
        self._logger.info("--- Phase 3: Aggregator ---")
        final_result = await self._run_aggregator(task, worker_results, conversation)
        total_turns += 1
        
        return self._make_result(
            success=final_result.get("success", False),
            turns_used=total_turns,
            error=final_result.get("error"),
        )
    
    async def _run_splitter(self, task: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Run the splitter agent to divide task into subtasks."""
        messages: List[LLMMessage] = [
            SystemMessage(content=SPLITTER_PROMPT),
            UserMessage(
                content=self._format_task_prompt(task),
                source="user",
            ),
        ]
        
        response = await super()._get_llm_response(self._model_client, messages, self._max_retries)
        if response:
            self._logger.info(f"Splitter response keys: {list(response.keys())}")
            
            # Try multiple extraction strategies
            subtasks = self._extract_subtasks(response)
            if subtasks:
                return subtasks
            
            self._logger.warning(f"Splitter response missing 'subtasks' key. Got keys: {list(response.keys())}")
            
            # Fallback: generate default subtasks based on task nodes
            return self._generate_default_subtasks(task)
        else:
            self._logger.warning("Splitter returned None response")
            return self._generate_default_subtasks(task)
    
    def _extract_subtasks(self, response: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract subtasks from various LLM response formats."""
        # Direct format: {"subtasks": [...]}
        if "subtasks" in response and isinstance(response["subtasks"], list):
            return response["subtasks"]
        
        # Nested in action_input: {"action_input": {"subtasks": [...]}}
        if "action_input" in response and isinstance(response["action_input"], dict):
            if "subtasks" in response["action_input"]:
                return response["action_input"]["subtasks"]
        
        # Look for any list that could be subtasks
        for key, value in response.items():
            if isinstance(value, list) and len(value) > 0:
                # Check if items look like subtasks (have id or description)
                if isinstance(value[0], dict) and ("id" in value[0] or "description" in value[0]):
                    self._logger.info(f"Extracted subtasks from key '{key}'")
                    return value
        
        return None
    
    def _generate_default_subtasks(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate default subtasks based on task topology nodes."""
        subtasks = []
        
        # Extract nodes from topology
        topology = task.get("topology", {})
        nodes = topology.get("nodes", [])
        
        if nodes:
            # Create one subtask per node for configuration
            for i, node in enumerate(nodes):
                node_name = node.get("name", f"node_{i}")
                subtasks.append({
                    "id": f"config_{node_name}",
                    "description": f"Configure {node_name}: set IP addresses and routing protocol"
                })
            
            # Add verification subtask
            subtasks.append({
                "id": "verify",
                "description": "Verify connectivity and routing convergence across all nodes"
            })
        else:
            # Fallback: single subtask with full task
            subtasks.append({
                "id": "full_task",
                "description": task.get("description", "Complete the configuration task")
            })
        
        self._logger.info(f"Generated {len(subtasks)} default subtasks from topology")
        return subtasks
    
    async def _run_worker(
        self,
        subtask: Dict[str, Any],
        full_task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
        start_time: float = 0.0,
        time_limit: float = 600.0,
    ) -> Dict[str, Any]:
        """Run a worker agent on a subtask."""
        # Include tool info from system_prompt (bug fix: workers need to know about tools)
        worker_system = self._system_prompt + "\n\n" + WORKER_PROMPT if self._system_prompt else WORKER_PROMPT
        
        # Include task context (node topology, interfaces, etc.)
        context = full_task.get("context", {})
        context_str = json.dumps(context, indent=2) if context else "{}"
        
        messages: List[LLMMessage] = [
            SystemMessage(content=worker_system),
            UserMessage(
                content=f"Main Task: {full_task.get('description', '')}\n\nContext:\n{context_str}\n\nYour Subtask: {subtask.get('description', '')}",
                source="user",
            ),
        ]
        
        max_turns = self._config.max_turns if hasattr(self._config, 'max_turns') else 10
        turn = 0
        result_summary = ""
        
        import time as time_pkg
        while turn < max_turns:
            # Check time limit
            elapsed = time_pkg.time() - start_time
            if elapsed >= time_limit:
                self._logger.warning(f"Time limit reached in worker: {elapsed:.1f}s >= {time_limit}s")
                break

            turn += 1
            response = await super()._get_llm_response(self._model_client, messages, self._max_retries)
            if not response:
                break
            
            action = response.get("action")
            action_input = response.get("action_input", {})
            thought = response.get("thought", "")
            
            self._log_reasoning(f"worker_{subtask.get('id', 'unknown')}", thought)
            
            if action == "subtask_complete":
                result_summary = action_input.get("result", "Completed")
                break
            
            # Execute action
            observation = await self._execute_action(action, action_input)
            self._log_action(action, action_input, observation)
            
            # Check for explicit session timeout or turn limit in observation
            if isinstance(observation, dict):
                error_type = observation.get("error")
                if error_type in ["time_limit_exceeded", "turn_limit_exceeded", "session_not_active"]:
                    self._logger.warning(f"Stopping worker due to session error: {error_type}")
                    break
            
            messages.append(AssistantMessage(content=json.dumps(response), source="assistant"))
            messages.append(UserMessage(content=f"OBSERVATION: {json.dumps(observation)}", source="user"))
        
        return {
            "subtask_id": subtask.get("id"),
            "turns": turn,
            "result": result_summary,
            "success": bool(result_summary),
        }
    
    async def _run_aggregator(
        self,
        task: Dict[str, Any],
        worker_results: List[Dict[str, Any]],
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """Run the aggregator agent to combine results."""
        results_summary = json.dumps(worker_results, indent=2)
        
        messages: List[LLMMessage] = [
            SystemMessage(content=AGGREGATOR_PROMPT),
            UserMessage(
                content=f"Task: {task.get('description', '')}\n\nWorker Results:\n{results_summary}",
                source="user",
            ),
        ]
        
        response = await super()._get_llm_response(self._model_client, messages, self._max_retries)
        if not response:
            return {"success": False, "error": "Aggregator failed to respond"}
        
        action = response.get("action")
        all_successful = response.get("all_successful", False)
        
        if action == "submit" and all_successful:
            observation = await self._execute_action("submit", {})
            return {"success": observation.get("success", False)}
        
        return {"success": False, "error": response.get("summary", "Aggregation failed")}
    
    def _make_result(
        self,
        success: bool,
        turns_used: int,
        error: str = None,
    ) -> Dict[str, Any]:
        return {
            "success": success,
            "turns_used": turns_used,
            "actions_executed": self._actions_executed,
            "reasoning_trace": self._reasoning_trace,
            "error": error,
            "token_usage": {
                "prompt_tokens": self._total_prompt_tokens,
                "completion_tokens": self._total_completion_tokens,
                "total_tokens": self._total_tokens,
            },
            "tool_usage": self._tool_calls,
        }
    
    def _format_task_prompt(self, task: Dict[str, Any]) -> str:
        context = task.get("context", {})
        context_str = json.dumps(context, indent=2) if context else "{}"
        return f"""Task ID: {task.get('task_id', 'unknown')}
Description: {task.get('description', '')}

Context:
{context_str}
"""
    
    async def _execute_action(self, action: Optional[str], action_input: Dict[str, Any]) -> Dict[str, Any]:
        if self._tool_executor is None:
            return {"success": False, "error": "No tool executor configured"}
        
        if action is None:
            return {"success": False, "error": "No action specified by LLM"}
        try:
            # Track tool usage
            self._tool_calls[action] = self._tool_calls.get(action, 0) + 1
            
            method = getattr(self._tool_executor, action, None)
            if method is None:
                return {"success": False, "error": f"Unknown action: {action}"}
            result = await method(**action_input)
            return result if isinstance(result, dict) else {"success": True, "result": result}
        except Exception as e:
            self._logger.error(f"Action execution error: {e}")
            return {"success": False, "error": str(e)}
    
    def _log_action(self, action: str, action_input: Dict[str, Any], result: Dict[str, Any]) -> None:
        entry = {"action": action, "input": action_input, "result": result}
        self._actions_executed.append(entry)
    
    def _log_reasoning(self, step: str, content: str) -> None:
        entry = {"step": step, "content": content}
        self._reasoning_trace.append(entry)
