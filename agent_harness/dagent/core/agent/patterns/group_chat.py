"""
Group Chat Pattern for Multi-Agent System.

Implements a group chat pattern where:
1. Multiple specialized agents participate in a discussion
2. A manager selects which agent speaks next
3. Agents take turns until the task is solved
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


MANAGER_PROMPT = """You coordinate a team to complete tasks. Select which agent speaks next.

Agents: {participants}

Guidelines:
- Analyzer: Use once at start to understand requirements
- Planner: Use once to create action plan
- Executor: Use repeatedly to run commands (most important!)
- Reviewer: Use after Executor is done to verify
- If stuck or no progress, select Executor

Output format (JSON only):
{{"reasoning": "why", "next_speaker": "AgentName", "instruction": "what to do"}}

To finish: {{"reasoning": "done", "next_speaker": "DONE", "instruction": ""}}
"""

PARTICIPANT_PROMPT_TEMPLATE = """You are {name}, a {role} agent.
{description}

Review the manager's instruction and act on it immediately.

Respond ONLY with this JSON (no other text):
{{
    "thought": "Brief reasoning about what to do",
    "action": "tool_name_to_call",
    "action_input": {{"param": "value"}}
}}

If no tool action needed (analysis/planning only):
{{
    "thought": "Your analysis or plan",
    "action": "none",
    "action_input": {{}}
}}
"""


# Default participant definitions
DEFAULT_PARTICIPANTS = [
    {
        "name": "Analyzer",
        "role": "analysis",
        "description": "Briefly identify the key requirements from the task context. Keep it to 2-3 bullet points. Do NOT use tools.",
    },
    {
        "name": "Planner",
        "role": "planning",
        "description": "Create a SHORT numbered list of commands/actions needed. Be specific with actual command syntax. Do NOT use tools.",
    },
    {
        "name": "Executor",
        "role": "execution",
        "description": "Execute the planned actions using tools. Call exec_command to configure devices. Work through the plan step by step, executing one command at a time.",
    },
    {
        "name": "Reviewer",
        "role": "review",
        "description": "Verify the configuration is complete. Use exec_command with 'show' commands to check status. Call submit when verified.",
    },
]


class GroupChatPattern(BasePattern):
    """
    Group chat multi-agent pattern: Manager coordinates specialized agents.
    
    This pattern:
    1. Maintains a shared conversation thread
    2. Manager selects next speaker based on context
    3. Participants contribute and take actions
    4. Continues until manager signals completion
    """
    
    def __init__(
        self,
        runtime: SingleThreadedAgentRuntime,
        config: Any,
        model_client: ChatCompletionClient,
        tool_executor: Any = None,
        system_prompt: str = None,
        participants: List[Dict[str, str]] = None,
        max_retries: int = 3,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize group chat pattern.
        
        Args:
            runtime: AutoGen Core runtime
            config: MAS configuration
            model_client: LLM client for all agents
            tool_executor: Object providing tool execution methods
            system_prompt: System prompt containing tool info
            participants: List of participant definitions
            max_retries: Max retries for parsing errors
            logger: Optional logger instance
        """
        super().__init__(runtime, config, logger)
        self._model_client = model_client
        self._tool_executor = tool_executor
        self._system_prompt = system_prompt or ""
        self._participants = participants or DEFAULT_PARTICIPANTS
        self._max_retries = max_retries
        
        # Execution state
        self._actions_executed: List[Dict[str, Any]] = []
        self._reasoning_trace: List[Dict[str, Any]] = []
        
        # Token and tool tracking
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._tool_calls: Dict[str, int] = {}
        
        # Agent conversation log (group chat messages)
        self._agent_conversations: List[Dict[str, Any]] = []
    
    async def register_agents(self) -> None:
        """Register agents for group chat pattern."""
        self._logger.debug("GroupChatPattern: No explicit agent registration needed")
    
    @property
    def entry_topic(self) -> str:
        return "group_chat"
    
    async def execute(
        self,
        task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """
        Execute group chat pattern on the task.
        """
        self._actions_executed = []
        self._reasoning_trace = []
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_tokens = 0
        self._tool_calls = {}
        self._agent_conversations = []
        
        task_id = task.get("task_id", "unknown")
        time_limit = task.get("time_limit", 600.0)
        self._logger.info(f"Starting GroupChatPattern on task: {task_id}")
        
        import time as time_pkg
        start_time = time_pkg.time()
        max_turns = self._config.max_turns if hasattr(self._config, 'max_turns') else 50
        turn = 0
        
        # Shared conversation thread
        chat_history: List[Dict[str, Any]] = []
        
        # Track which agents have contributed (for intelligent fallback)
        agent_turns: Dict[str, int] = {"Analyzer": 0, "Planner": 0, "Executor": 0, "Reviewer": 0}
        commands_executed = 0
        
        # Initial task message
        chat_history.append({
            "speaker": "User",
            "content": f"Task: {task.get('description', '')}",
        })
        
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
            self._logger.info(f"--- Turn {turn} ---")
            
            # LLM-based manager selection
            selection = await self._run_manager(task, chat_history)
            
            # Parse selection with fallbacks for various LLM response formats
            selection = self._parse_manager_selection(selection)
            
            # Intelligent fallback if manager fails
            if not selection or not selection.get("next_speaker"):
                selection = self._get_fallback_selection(turn, agent_turns, commands_executed)
                self._logger.info(f"Using fallback selection: {selection['next_speaker']}")
            
            next_speaker = selection.get("next_speaker")
            instruction = selection.get("instruction", "")
            
            self._log_reasoning(f"manager_turn{turn}", f"Selected: {next_speaker}")
            
            # Check if done
            if next_speaker == "DONE":
                self._logger.info("Manager signaled completion")
                # Submit result
                observation = await self._execute_action("submit", {})
                return self._make_result(
                    success=observation.get("success", False),
                    turns_used=turn,
                )
            
            # Find participant
            participant = self._get_participant(next_speaker)
            if not participant:
                self._logger.warning(f"Unknown participant: {next_speaker}")
                continue
            
            # Run selected participant
            response = await self._run_participant(participant, task, chat_history, instruction)
            
            if response:
                # Track agent participation
                agent_turns[next_speaker] = agent_turns.get(next_speaker, 0) + 1
                
                # Add to chat history
                thought = response.get("thought", "")
                chat_history.append({
                    "speaker": participant["name"],
                    "content": thought,
                })
                
                # Log agent conversation
                self._agent_conversations.append({
                    "from_agent": participant["name"],
                    "to_agent": "group",
                    "turn": turn,
                    "content_type": "contribution",
                    "content": response,
                    "timestamp": datetime.now().isoformat(),
                })
                
                self._log_reasoning(f"{participant['name']}_turn{turn}", thought)
                
                # Execute action if any
                action = response.get("action")
                if action and action != "none":
                    action_input = response.get("action_input", {}) or {}
                    observation = await self._execute_action(action, action_input)
                    self._log_action(action, action_input, observation)
                    
                    # Track command execution
                    if action == "exec_command":
                        commands_executed += 1
                    
                    # Check for session errors
                    if isinstance(observation, dict):
                        error_type = observation.get("error")
                        if error_type in ["time_limit_exceeded", "turn_limit_exceeded", "session_not_active"]:
                            self._logger.warning(f"Stopping execution due to session error: {error_type}")
                            return self._make_result(
                                success=False,
                                turns_used=turn,
                                error=f"Session ended: {error_type}",
                            )
                    
                    # Add observation to chat (summarized to avoid context bloat)
                    obs_summary = self._summarize_observation(observation)
                    chat_history.append({
                        "speaker": "System",
                        "content": f"Result: {obs_summary}",
                    })
        
        return self._make_result(
            success=False,
            turns_used=turn,
            error="Turn limit reached",
        )
    
    async def _run_manager(
        self,
        task: Dict[str, Any],
        chat_history: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Run manager to select next speaker."""
        # Format participants list
        participants_text = "\n".join([
            f"- {p['name']}: {p['role']} - {p['description']}"
            for p in self._participants
        ])
        
        # Format chat history
        history_text = self._format_chat_history(chat_history)
        
        prompt = MANAGER_PROMPT.format(participants=participants_text)
        
        messages: List[LLMMessage] = [
            SystemMessage(content=prompt),
            UserMessage(
                content=f"Task: {task.get('description', '')}\n\nConversation so far:\n{history_text}\n\nSelect the next speaker.",
                source="user",
            ),
        ]
        
        return await super()._get_llm_response(self._model_client, messages, self._max_retries)
    
    def _parse_manager_selection(self, selection: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Parse manager selection with support for various LLM response formats."""
        if not selection:
            return None
        
        # Check for nested format: {"action": "...", "action_input": {"next_speaker": "..."}}
        if "next_speaker" not in selection and "action_input" in selection:
            if isinstance(selection["action_input"], dict) and "next_speaker" in selection["action_input"]:
                self._logger.debug("Extracted next_speaker from nested action_input")
                return selection["action_input"]
        
        # Check for alternative key names
        if "next_speaker" not in selection:
            for alt_key in ["selected_speaker", "speaker", "participant", "agent", "chosen"]:
                if alt_key in selection:
                    selection["next_speaker"] = selection[alt_key]
                    self._logger.debug(f"Mapped {alt_key} to next_speaker")
                    break
        
        return selection
    
    def _get_fallback_selection(
        self, turn: int, agent_turns: Dict[str, int], commands_executed: int
    ) -> Dict[str, Any]:
        """Get intelligent fallback selection based on conversation state."""
        # If no analysis yet, start with Analyzer
        if agent_turns.get("Analyzer", 0) == 0:
            return {"next_speaker": "Analyzer", "instruction": "Analyze the task requirements briefly."}
        
        # If no plan yet, use Planner
        if agent_turns.get("Planner", 0) == 0:
            return {"next_speaker": "Planner", "instruction": "Create an action plan with specific commands."}
        
        # If no commands executed, definitely need Executor
        if commands_executed == 0:
            return {"next_speaker": "Executor", "instruction": "Start executing the planned configuration commands."}
        
        # If many commands executed, maybe time for review
        if commands_executed > 10 and agent_turns.get("Reviewer", 0) == 0:
            return {"next_speaker": "Reviewer", "instruction": "Verify the configuration is complete."}
        
        # Default: keep executing
        return {"next_speaker": "Executor", "instruction": "Continue executing configuration commands."}
    
    def _summarize_observation(self, observation: Any) -> str:
        """Summarize observation to avoid context bloat."""
        if not isinstance(observation, dict):
            return str(observation)[:200]
        
        # For command results, show success/failure and brief output
        success = observation.get("success", False)
        stdout = observation.get("stdout", "")
        error = observation.get("error", "")
        
        if error:
            return f"Error: {error}"
        elif success:
            # Truncate long output
            if len(stdout) > 150:
                return f"Success: {stdout[:150]}..."
            return f"Success: {stdout}" if stdout else "Success"
        else:
            return f"Failed: {stdout[:150]}..." if len(stdout) > 150 else f"Failed: {stdout}"
    
    async def _run_participant(
        self,
        participant: Dict[str, str],
        task: Dict[str, Any],
        chat_history: List[Dict[str, Any]],
        instruction: str,
    ) -> Optional[Dict[str, Any]]:
        """Run a participant agent."""
        history_text = self._format_chat_history(chat_history)
        
        prompt = PARTICIPANT_PROMPT_TEMPLATE.format(
            name=participant["name"],
            role=participant["role"],
            description=participant["description"],
        )
        
        # Add tool info for executor-type participants
        if participant["role"] == "execution" and self._system_prompt:
            prompt = self._system_prompt + "\n\n" + prompt
        
        # Include task context for executor-type participants
        task_prompt = self._format_task_prompt(task) if participant["role"] == "execution" else f"Task: {task.get('description', '')}"
        
        messages: List[LLMMessage] = [
            SystemMessage(content=prompt),
            UserMessage(
                content=f"{task_prompt}\n\nConversation:\n{history_text}\n\nManager instruction: {instruction}\n\nProvide your contribution.",
                source="user",
            ),
        ]
        
        return await super()._get_llm_response(self._model_client, messages, self._max_retries)
    
    def _get_participant(self, name: Optional[str]) -> Optional[Dict[str, str]]:
        """Get participant by name."""
        if name is None:
            return None
        for p in self._participants:
            if p["name"].lower() == name.lower():
                return p
        return None
    
    def _format_chat_history(self, chat_history: List[Dict[str, Any]]) -> str:
        """Format chat history for display."""
        if not chat_history:
            return "(No messages yet)"
        
        lines = []
        for entry in chat_history[-10:]:  # Last 10 messages for context
            speaker = entry.get("speaker", "Unknown")
            content = entry.get("content", "")
            lines.append(f"[{speaker}]: {content}")
        
        return "\n\n".join(lines)
    
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
            "agent_conversations": self._agent_conversations,
        }
    
    async def _execute_action(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        if self._tool_executor is None:
            return {"success": False, "error": "No tool executor configured"}
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
    
    def _format_task_prompt(self, task: Dict[str, Any]) -> str:
        """Format the task as a prompt for the LLM."""
        context = task.get("context", {})
        context_str = json.dumps(context, indent=2) if context else "{}"
        return f"""Task ID: {task.get('task_id', 'unknown')}
Description: {task.get('description', '')}

Context:
{context_str}
"""
