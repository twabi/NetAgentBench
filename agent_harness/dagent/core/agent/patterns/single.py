"""
Single Agent Pattern for Multi-Agent System.

Implements a single LLM agent with ReAct-style (Reason → Act → Observe) loop.
This is the simplest pattern - one agent processes the task directly.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from autogen_core import (
    SingleThreadedAgentRuntime,
    TopicId,
    TypeSubscription,
)
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


DEFAULT_SYSTEM_PROMPT = """You are an AI assistant that solves tasks by executing tool actions.

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanations, no markdown, no text before or after the JSON.

JSON FORMAT (respond with ONLY this, nothing else):
{
    "thought": "Brief reasoning about what to do next",
    "action": "tool_name",
    "action_input": {"param1": "value1"}
}

To finish the task:
{
    "thought": "Task complete",
    "action": "finish",
    "action_input": {}
}

RULES:
- Output ONLY the JSON object
- NO markdown code blocks
- NO explanations before or after
- NO step-by-step instructions
- Just the raw JSON object
"""


class SingleAgentPattern(BasePattern):
    """
    Single agent with ReAct-style reasoning loop.
    
    This pattern uses a single LLM to:
    1. Reason about the task
    2. Execute actions via tool executor
    3. Observe results and iterate
    
    The loop continues until the agent signals completion
    or the turn limit is reached.
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
        Initialize single agent pattern.
        
        Args:
            runtime: AutoGen Core runtime
            config: MAS configuration
            model_client: LLM client for reasoning
            tool_executor: Object providing tool execution methods
            system_prompt: Custom system prompt (uses default if not provided)
            max_retries: Max retries for parsing errors
            logger: Optional logger instance
        """
        super().__init__(runtime, config, logger)
        self._model_client = model_client
        self._tool_executor = tool_executor
        self._max_retries = max_retries
        
        # Detect if the model supports JSON output mode (OpenAI models)
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        self._supports_json_mode = isinstance(model_client, OpenAIChatCompletionClient)
        
        # Use provided or default system prompt
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        if self._supports_json_mode:
            self._logger.info("Using OpenAI model with forced JSON output mode")
        else:
            self._logger.info("Using text-based JSON response mode")
        
        # Execution state
        self._actions_executed: List[Dict[str, Any]] = []
        self._reasoning_trace: List[Dict[str, Any]] = []
        
        # Token and tool tracking
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._tool_calls: Dict[str, int] = {}
    
    async def register_agents(self) -> None:
        """
        Register the single agent.
        
        For this pattern, we don't use the pub/sub model - we directly
        drive the ReAct loop from execute(). No agent registration needed.
        """
        self._logger.debug("SingleAgentPattern: No agent registration needed")
    
    @property
    def entry_topic(self) -> str:
        """Entry topic (not used for single agent pattern)."""
        return "single_agent"
    
    async def execute(
        self,
        task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """
        Execute ReAct loop on the task.
        
        Args:
            task: Task definition with task_id, description, context, etc.
            conversation: Optional conversation for multi-turn context
            
        Returns:
            Result dict with success, turns_used, actions_executed, etc.
        """
        # Reset state
        self._actions_executed = []
        self._reasoning_trace = []
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_tokens = 0
        self._tool_calls = {}
        
        # Build initial messages
        messages: List[LLMMessage] = []
        
        # If multi-turn, prepend conversation history
        if conversation and conversation.messages:
            messages.extend(conversation.messages)
            self._logger.debug(f"Using {len(conversation.messages)} messages from conversation history")
        
        # Add system prompt and task
        messages.append(SystemMessage(content=self._system_prompt))
        messages.append(UserMessage(
            content=self._format_task_prompt(task),
            source="user",
        ))
        
        task_id = task.get("task_id", "unknown")
        max_turns = self._config.max_turns if hasattr(self._config, 'max_turns') else 50
        time_limit = task.get("time_limit", 600.0)
        
        self._logger.info(f"Starting SingleAgentPattern on task: {task_id}")
        
        import time as time_pkg  # Use distinct name to avoid conflict with 'time' variable
        start_time = time_pkg.time()
        turn = 0
        
        try:
            while turn < max_turns:
                # Check time limit
                elapsed = time_pkg.time() - start_time
                if elapsed >= time_limit:
                    self._logger.warning(f"Time limit reached: {elapsed:.1f}s >= {time_limit}s")
                    return self._make_result(
                        success=False,
                        turns_used=turn,
                        error="Time limit reached",
                    )

                turn += 1
                self._logger.debug(f"Turn {turn}/{max_turns}")
                
                # Log system prompt to verify tools are present (debug only)
                if turn == 1:
                    sys_msg = next((m for m in messages if isinstance(m, SystemMessage)), None)
                    if sys_msg:
                        self._logger.info(f"System Prompt (first 500 chars): {sys_msg.content[:500]}")
                        self._logger.debug(f"Full System Prompt: {sys_msg.content}")

                # Get LLM response
                response = await self._get_llm_response(messages)
                if response is None:
                    return self._make_result(
                        success=False,
                        turns_used=turn,
                        error="Failed to get valid LLM response",
                    )
                
                thought = response.get("thought", "")
                action = response.get("action", "")
                action_input = response.get("action_input", {})
                
                self._log_reasoning("thought", thought)
                self._log_reasoning("action", f"{action}: {action_input}")
                
                # Check for finish. Treat 'finish' as an implicit 'submit' so the
                # benchmark session terminates cleanly (termination_reason=submitted)
                # instead of being left active and reported as 'unknown'.
                if action == "finish":
                    self._logger.info("Agent signaled finish; issuing implicit submit")
                    submit_obs = await self._execute_action("submit", {})
                    self._log_reasoning("action", "submit: {} (implicit on finish)")
                    self._log_reasoning("observation", str(submit_obs))
                    self._log_action("submit", {}, submit_obs)
                    if conversation:
                        for msg in messages[len(conversation.messages):]:
                            conversation.add_message(msg)
                    return self._make_result(
                        success=bool(isinstance(submit_obs, dict) and submit_obs.get("success", False)),
                        turns_used=turn,
                    )
                
                # Execute action
                observation = await self._execute_action(action, action_input)
                self._log_reasoning("observation", str(observation))
                self._log_action(action, action_input, observation)
                
                # Check for explicit session timeout or turn limit in observation
                # This prevents the agent from looping when the session is already closed
                if isinstance(observation, dict):
                    error_type = observation.get("error")
                    if error_type in ["time_limit_exceeded", "turn_limit_exceeded", "session_not_active"]:
                        self._logger.warning(f"Stopping execution due to session error: {error_type}")
                        return self._make_result(
                            success=False,
                            turns_used=turn,
                            error=f"Session ended: {error_type}",
                        )
                
                # Check if action indicates task completion
                if self._is_task_complete(action, observation):
                    # Update conversation history if provided
                    if conversation:
                        for msg in messages[len(conversation.messages):]:
                            conversation.add_message(msg)
                    
                    return self._make_result(
                        success=True,
                        turns_used=turn,
                    )
                
                # Add observation to messages
                messages.append(UserMessage(
                    content=f"OBSERVATION: {json.dumps(observation)}",
                    source="system",
                ))
            
            # Update conversation history if provided
            if conversation:
                for msg in messages[len(conversation.messages):]:
                    conversation.add_message(msg)
            
            # Ran out of turns or finished without explicit success
            return self._make_result(
                success=False,
                turns_used=turn,
                error="Turn limit reached" if turn >= max_turns else None,
            )
            
        except Exception as e:
            self._logger.error(f"Error solving task: {e}")
            return self._make_result(
                success=False,
                turns_used=turn,
                error=str(e),
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
        }
    
    def _format_task_prompt(self, task: Dict[str, Any]) -> str:
        """Show the end goal and the topology. Hide checkers, properties, and research notes."""
        context = task.get("context") or {}
        topology = context.get("topology")
        topology_text = json.dumps(topology, indent=2) if topology else "(not specified)"
        prompt_parts = [
            f"Task ID: {task.get('task_id', 'unknown')}",
            "Goal:",
            task.get("description", ""),
            "",
            "Topology:",
            topology_text,
            "",
            "Instructions:",
            "1. The goal is the end state the network must reach.",
            "2. The topology lists the nodes and links.",
            "3. Inspect the live network and configure it until that end state holds.",
            "4. Consider calling 'get_session_status' early to see your turn and time budget.",
            "5. Verify with read commands before you finish.",
            "6. Call 'submit' when the goal is met.",
        ]
        return "\n".join(prompt_parts)
    
    def _is_task_complete(self, action: str, observation: Dict[str, Any]) -> bool:
        """
        Check if the task is complete based on action and observation.
        
        Default: check for 'submit' action with successful result.
        """
        if action == "submit" and observation.get("success", False):
            return True
        return False
    
    async def _get_llm_response(self, messages: List[LLMMessage]) -> Optional[Dict[str, Any]]:
        """Get and parse LLM response with retries."""
        parsed = await super()._get_llm_response(
            model_client=self._model_client,
            messages=messages,
            max_retries=self._max_retries,
            json_output=self._supports_json_mode
        )
        if parsed:
            # Reconstruct text for history (approximated)
            text = json.dumps(parsed)
            messages.append(AssistantMessage(content=text, source="assistant"))
        return parsed
    
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
            
            # Try to get the method from tool_executor
            method = getattr(self._tool_executor, action, None)
            if method is None:
                return {"success": False, "error": f"Unknown action: {action}"}
            
            # Call the method with action_input as kwargs
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
