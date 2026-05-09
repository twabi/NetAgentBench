"""
Sequential Pattern for Multi-Agent System.

Implements a Planner → Executor → Verifier flow where:
1. Planner: Analyzes task and creates a step-by-step plan
2. Executor: Executes the plan using tools (ReAct loop)
3. Verifier: Reviews execution and submits result
"""

import json
import logging
from datetime import datetime
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


PLANNER_PROMPT = """You are a PLANNING AGENT.
Your goal is to analyze the request and create a step-by-step plan.

Review the task description and context.
Break down the task into logical steps.
For each step, specify what needs to be done.

Respond in JSON format:
{
    "analysis": "Your analysis of the task",
    "plan": [
        "Step 1: description",
        "Step 2: description",
        ...
    ]
}
"""

EXECUTOR_PROMPT = """You are an EXECUTION AGENT.
Your goal is to execute the given plan using the available tools.

Follow the plan carefully.
Report progress as you go.

Respond in JSON format:
{
    "thought": "Reasoning about current step",
    "action": "tool_name",
    "action_input": {...}
}

When finished executing the plan, respond with:
{
    "thought": "Plan execution complete",
    "action": "finish_execution",
    "action_input": {}
}
"""

VERIFIER_PROMPT = """You are a VERIFICATION AGENT.
Your goal is to verify that the task was completed correctly.

Review the executed actions and results.
If everything looks correct, submit the solution.
If there are issues, describe them.

Respond in JSON format:
{
    "analysis": "Review of the execution",
    "verdict": "pass" or "fail",
    "action": "submit" (if pass) or "retry" (if fail),
    "reason": "Explanation of verdict"
}
"""


class SequentialPattern(BasePattern):
    """
    Sequential multi-agent structure: Planner → Executor → Verifier.
    
    This pattern divides the work across three phases:
    1. Planner: Creates a high-level plan
    2. Executor: Executes the plan using tools (ReAct loop)
    3. Verifier: Reviews the work and submits
    
    Each phase uses the same underlying LLM but with different
    system prompts that define distinctive agent personas.
    """
    
    def __init__(
        self,
        runtime: SingleThreadedAgentRuntime,
        config: Any,
        model_client: ChatCompletionClient,
        tool_executor: Any = None,
        system_prompt: str = None,
        max_retries: int = 3,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize sequential pattern.
        
        Args:
            runtime: AutoGen Core runtime
            config: MAS configuration
            model_client: LLM client for all three agents
            tool_executor: Object providing tool execution methods
            system_prompt: System prompt containing tool info for executor
            max_retries: Max retries for parsing errors
            logger: Optional logger instance
        """
        super().__init__(runtime, config, logger)
        self._model_client = model_client
        self._tool_executor = tool_executor
        self._system_prompt = system_prompt or ""
        self._max_retries = max_retries
        
        # Execution state
        self._actions_executed: List[Dict[str, Any]] = []
        self._reasoning_trace: List[Dict[str, Any]] = []
        
        # Token and tool tracking
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._tool_calls: Dict[str, int] = {}
        
        # Agent conversation log (for multi-agent patterns)
        self._agent_conversations: List[Dict[str, Any]] = []
    
    async def register_agents(self) -> None:
        """
        Register agents for sequential pattern.
        
        For this pattern, we directly drive the phases rather than
        using pub/sub, so no explicit agent registration is needed.
        """
        self._logger.debug("SequentialPattern: No explicit agent registration needed")
    
    @property
    def entry_topic(self) -> str:
        """Entry topic (not used for sequential pattern)."""
        return "sequential"
    
    async def execute(
        self,
        task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """
        Execute sequential phases on the task.
        
        Args:
            task: Task definition
            conversation: Optional conversation for multi-turn context
            
        Returns:
            Result dict with success, turns_used, etc.
        """
        # Reset state
        self._actions_executed = []
        self._reasoning_trace = []
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_tokens = 0
        self._tool_calls = {}
        self._agent_conversations = []
        
        task_id = task.get("task_id", "unknown")
        time_limit = task.get("time_limit", 600.0)
        self._logger.info(f"Starting SequentialPattern on task: {task_id}")
        
        import time as time_pkg
        start_time = time_pkg.time()
        
        # 1. PLANNER PHASE
        self._logger.info("--- Phase 1: Planner ---")
        plan = await self._run_planner(task, conversation)
        if not plan:
            return self._make_result(
                success=False,
                turns_used=1,
                error="Planner failed to generate plan",
            )
        
        self._log_reasoning("plan", json.dumps(plan, indent=2))
        
        # 2. EXECUTOR PHASE
        self._logger.info("--- Phase 2: Executor ---")
        exec_turns = await self._run_executor(task, plan, conversation, start_time=start_time, time_limit=time_limit)
        
        # 3. VERIFIER PHASE
        self._logger.info("--- Phase 3: Verifier ---")
        final_result = await self._run_verifier(task, exec_turns, conversation)
        
        return final_result
    
    async def _run_planner(
        self, 
        task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run the planner agent."""
        messages: List[LLMMessage] = []
        
        # Include conversation history if multi-turn
        if conversation and conversation.messages:
            messages.extend(conversation.messages)
        
        messages.extend([
            SystemMessage(content=PLANNER_PROMPT),
            UserMessage(
                content=self._format_task_prompt(task),
                source="user",
            ),
        ])
        
        response = await super()._get_llm_response(self._model_client, messages, self._max_retries)
        if response:
            self._logger.info(f"Planner response keys: {list(response.keys())}")
            
            # Handle both formats:
            # 1. Direct format: {"analysis": "...", "plan": [...]}
            # 2. Nested format: {"action": "create_plan", "action_input": {"analysis": "...", "plan": [...]}}
            plan_data = None
            if "plan" in response:
                plan_data = response
            elif "action_input" in response and isinstance(response["action_input"], dict):
                if "plan" in response["action_input"]:
                    # Extract the nested plan data
                    plan_data = response["action_input"]
                    self._logger.info("Extracted plan from nested action_input format")
            
            if plan_data:
                # Log agent conversation
                self._agent_conversations.append({
                    "from_agent": "planner",
                    "to_agent": "executor",
                    "content_type": "plan",
                    "content": plan_data,
                    "timestamp": datetime.now().isoformat(),
                })
                # Save to conversation
                if conversation:
                    conversation.add_message(AssistantMessage(
                        content=json.dumps(plan_data),
                        source="planner"
                    ))
                return plan_data
            else:
                self._logger.warning(f"Planner response missing 'plan' key. Got: {response}")
        else:
            self._logger.warning("Planner returned None response")
        return None
    
    async def _run_executor(
        self, 
        task: Dict[str, Any], 
        plan: Dict[str, Any],
        conversation: Optional[Conversation] = None,
        start_time: float = 0.0,
        time_limit: float = 600.0,
    ) -> int:
        """Run the executor agent loop. Returns turns used."""
        # Combine tool info from system_prompt with executor instructions
        executor_system = self._system_prompt + "\n\n" + EXECUTOR_PROMPT if self._system_prompt else EXECUTOR_PROMPT
        
        # Include full task context (node topology, interfaces, etc.) like single agent
        context = task.get("context", {})
        context_str = json.dumps(context, indent=2) if context else "{}"
        
        messages: List[LLMMessage] = [
            SystemMessage(content=executor_system),
            UserMessage(
                content=f"Task: {task.get('description', '')}\n\nContext:\n{context_str}\n\nPlan:\n{json.dumps(plan.get('plan', []), indent=2)}\n\nExecute this plan using the available tools.",
                source="user",
            ),
        ]
        
        max_turns = self._config.max_turns if hasattr(self._config, 'max_turns') else 50
        turn = 0
        
        import time as time_pkg
        while turn < max_turns:
            # Check time limit
            elapsed = time_pkg.time() - start_time
            if elapsed >= time_limit:
                self._logger.warning(f"Time limit reached in executor: {elapsed:.1f}s >= {time_limit}s")
                break

            turn += 1
            response = await super()._get_llm_response(self._model_client, messages, self._max_retries)
            if not response:
                break
            
            action = response.get("action")
            action_input = response.get("action_input", {})
            thought = response.get("thought", "")
            
            self._log_reasoning("executor_thought", thought)
            self._log_reasoning("executor_action", f"{action}: {action_input}")
            
            if action == "finish_execution":
                break
                
            # Execute action
            observation = await self._execute_action(action, action_input)
            self._log_action(action, action_input, observation)
            
            # Check for explicit session timeout or turn limit in observation
            if isinstance(observation, dict):
                error_type = observation.get("error")
                if error_type in ["time_limit_exceeded", "turn_limit_exceeded", "session_not_active"]:
                    self._logger.warning(f"Stopping executor due to session error: {error_type}")
                    break
            
            messages.append(AssistantMessage(content=json.dumps(response), source="assistant"))
            messages.append(UserMessage(content=f"OBSERVATION: {json.dumps(observation)}", source="user"))
        
        # Log executor summary as agent conversation
        self._agent_conversations.append({
            "from_agent": "executor",
            "to_agent": "verifier",
            "content_type": "execution_summary",
            "content": {
                "turns": turn,
                "actions_count": len(self._actions_executed),
            },
            "timestamp": datetime.now().isoformat(),
        })
        
        # Save executor summary to conversation
        if conversation:
            conversation.add_message(AssistantMessage(
                content=f"Executed {turn} turns, {len(self._actions_executed)} actions",
                source="executor"
            ))
            
        return turn
    
    async def _run_verifier(
        self, 
        task: Dict[str, Any], 
        exec_turns: int,
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """Run the verifier agent."""
        # Summarize actions for verifier
        actions_summary = json.dumps(self._actions_executed, indent=2)
        
        messages: List[LLMMessage] = [
            SystemMessage(content=VERIFIER_PROMPT),
            UserMessage(
                content=f"Task: {task.get('description', '')}\n\nExecuted Actions:\n{actions_summary}\n\nVerify and submit if correct.",
                source="user",
            ),
        ]
        
        response = await super()._get_llm_response(self._model_client, messages, self._max_retries)
        if not response:
            return self._make_result(
                success=False,
                turns_used=exec_turns + 1,
                error="Verifier failed to respond",
            )
            
        action = response.get("action")
        verdict = response.get("verdict")
        reason = response.get("reason", "")
        
        self._log_reasoning("verifier_verdict", f"{verdict}: {reason}")
        
        # Save verifier result to conversation
        if conversation:
            conversation.add_message(AssistantMessage(
                content=f"Verdict: {verdict}, Action: {action}",
                source="verifier"
            ))
        
        if action == "submit":
            # Actually call submit tool
            observation = await self._execute_action("submit", {})
            success = observation.get("success", False)
            if success:
                return self._make_result(
                    success=True,
                    turns_used=exec_turns + 1,
                )
        
        return self._make_result(
            success=False,
            turns_used=exec_turns + 1,
            error=f"Verification failed: {reason}",
        )
    
    def _make_result(
        self,
        success: bool,
        turns_used: int,
        error: str = None,
    ) -> Dict[str, Any]:
        """Create result dictionary."""
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
            "agent_conversations": self._agent_conversations,
        }
    
    async def _execute_action(
        self,
        action: Optional[str],
        action_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an action via tool executor."""
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
    
    def _log_action(
        self,
        action: str,
        action_input: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Log an action execution."""
        entry = {
            "action": action,
            "input": action_input,
            "result": result,
        }
        self._actions_executed.append(entry)
        self._logger.debug(f"Action: {action} -> {result.get('success', False)}")
    
    def _log_reasoning(self, step: str, content: str) -> None:
        """Log a reasoning step."""
        entry = {"step": step, "content": content}
        self._reasoning_trace.append(entry)
        self._logger.debug(f"Reasoning [{step}]: {content[:100]}...")
    
    def _format_task_prompt(self, task: Dict[str, Any]) -> str:
        """Format the task as a prompt for the LLM."""
        context = task.get("context", {})
        context_str = json.dumps(context, indent=2) if context else "{}"
        return f"""Task ID: {task.get('task_id', 'unknown')}
Description: {task.get('description', '')}

Context:
{context_str}
"""
