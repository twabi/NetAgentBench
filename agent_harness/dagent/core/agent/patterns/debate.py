"""
Debate Pattern for Multi-Agent System.

Implements an adversarial debate pattern where:
1. Two or more agents argue different perspectives
2. They exchange rounds of arguments
3. A judge evaluates and selects the best approach
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


PROPONENT_PROMPT = """You are a PROPONENT AGENT in a debate.
Your goal is to argue FOR the proposed approach to solving the task.

Present strong arguments for why this approach is correct.
Address any counterarguments from the opponent.
Be persuasive but truthful.

Respond in JSON format:
{
    "argument": "Your argument for this round",
    "key_points": ["Point 1", "Point 2", ...],
    "response_to_opponent": "Your rebuttal to opponent's last argument (if any)"
}
"""

OPPONENT_PROMPT = """You are an OPPONENT AGENT in a debate.
Your goal is to critically examine the proposed approach and identify potential issues.

Present counterarguments and alternative approaches.
Point out flaws in the proponent's reasoning.
Be constructive in your criticism.

Respond in JSON format:
{
    "argument": "Your counterargument for this round",
    "issues_identified": ["Issue 1", "Issue 2", ...],
    "alternative_approach": "Your suggested alternative (if any)"
}
"""

JUDGE_PROMPT = """You are a JUDGE AGENT evaluating a debate.
Your goal is to evaluate the arguments and determine the best approach.

Review the debate transcript.
Evaluate the strength of each side's arguments.
Determine which approach is most likely to succeed.

Respond in JSON format:
{
    "analysis": "Your analysis of the debate",
    "winner": "proponent" or "opponent",
    "reasoning": "Why this side won",
    "final_approach": "The approach to use based on the debate",
    "action": "proceed" or "need_more_debate"
}
"""

EXECUTOR_PROMPT = """You are an EXECUTOR AGENT.
Your goal is to implement the approach determined by the debate.

Use the available tools to execute the chosen approach.

Respond in JSON format:
{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": {...}
}

When complete, respond with:
{
    "thought": "Execution complete",
    "action": "finish",
    "action_input": {}
}
"""


class DebatePattern(BasePattern):
    """
    Debate multi-agent pattern: Proponent vs Opponent → Judge → Execute.
    
    This pattern:
    1. Proponent argues for an approach
    2. Opponent critiques and suggests alternatives
    3. Multiple rounds of debate
    4. Judge determines best approach
    5. Executor implements the chosen approach
    """
    
    def __init__(
        self,
        runtime: SingleThreadedAgentRuntime,
        config: Any,
        model_client: ChatCompletionClient,
        tool_executor: Any = None,
        system_prompt: str = None,
        max_debate_rounds: int = 3,
        max_retries: int = 3,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize debate pattern.
        
        Args:
            runtime: AutoGen Core runtime
            config: MAS configuration
            model_client: LLM client for all agents
            tool_executor: Object providing tool execution methods
            system_prompt: System prompt containing tool info for executor
            max_debate_rounds: Maximum rounds of debate
            max_retries: Max retries for parsing errors
            logger: Optional logger instance
        """
        super().__init__(runtime, config, logger)
        self._model_client = model_client
        self._tool_executor = tool_executor
        self._system_prompt = system_prompt or ""
        self._max_debate_rounds = max_debate_rounds
        if hasattr(config, 'max_debate_rounds'):
            self._max_debate_rounds = config.max_debate_rounds
        self._max_retries = max_retries
        
        # Execution state
        self._actions_executed: List[Dict[str, Any]] = []
        self._reasoning_trace: List[Dict[str, Any]] = []
        
        # Token and tool tracking
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._tool_calls: Dict[str, int] = {}
        
        # Agent conversation log (debate exchanges)
        self._agent_conversations: List[Dict[str, Any]] = []
    
    async def register_agents(self) -> None:
        """Register agents for debate pattern."""
        self._logger.debug("DebatePattern: No explicit agent registration needed")
    
    @property
    def entry_topic(self) -> str:
        return "debate"
    
    async def execute(
        self,
        task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """
        Execute debate pattern on the task.
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
        self._logger.info(f"Starting DebatePattern on task: {task_id}")
        
        import time as time_pkg
        start_time = time_pkg.time()
        total_turns = 0
        debate_transcript: List[Dict[str, Any]] = []
        
        # DEBATE PHASE: Multiple rounds of proponent vs opponent
        for round_num in range(1, self._max_debate_rounds + 1):
            # Check time limit
            elapsed = time_pkg.time() - start_time
            if elapsed >= time_limit:
                self._logger.warning(f"Time limit reached during debate: {elapsed:.1f}s >= {time_limit}s")
                return self._make_result(
                    success=False,
                    turns_used=total_turns,
                    error="Time limit reached",
                )
            self._logger.info(f"--- Debate Round {round_num} ---")
            
            # Proponent turn
            proponent_response = await self._run_proponent(task, debate_transcript)
            total_turns += 1
            if proponent_response:
                debate_transcript.append({"role": "proponent", "round": round_num, **proponent_response})
                self._log_reasoning(f"proponent_r{round_num}", proponent_response.get("argument", ""))
                # Log debate exchange
                self._agent_conversations.append({
                    "from_agent": "proponent",
                    "to_agent": "opponent",
                    "round": round_num,
                    "content_type": "argument",
                    "content": proponent_response,
                    "timestamp": datetime.now().isoformat(),
                })
            
            # Opponent turn
            opponent_response = await self._run_opponent(task, debate_transcript)
            total_turns += 1
            if opponent_response:
                debate_transcript.append({"role": "opponent", "round": round_num, **opponent_response})
                self._log_reasoning(f"opponent_r{round_num}", opponent_response.get("argument", ""))
                # Log debate exchange
                self._agent_conversations.append({
                    "from_agent": "opponent",
                    "to_agent": "proponent",
                    "round": round_num,
                    "content_type": "counterargument",
                    "content": opponent_response,
                    "timestamp": datetime.now().isoformat(),
                })
        
        # JUDGING PHASE
        self._logger.info("--- Judging Phase ---")
        judgment = await self._run_judge(task, debate_transcript)
        total_turns += 1
        
        if not judgment:
            return self._make_result(
                success=False,
                turns_used=total_turns,
                error="Judge failed to evaluate debate",
            )
        
        self._log_reasoning("judgment", json.dumps(judgment, indent=2))
        
        # EXECUTION PHASE: Implement chosen approach
        self._logger.info("--- Execution Phase ---")
        exec_turns = await self._run_executor(task, judgment, conversation)
        total_turns += exec_turns
        
        # Submit result
        observation = await self._execute_action("submit", {})
        success = observation.get("success", False)
        
        return self._make_result(
            success=success,
            turns_used=total_turns,
            error=None if success else "Execution failed",
        )
    
    async def _run_proponent(
        self,
        task: Dict[str, Any],
        transcript: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Run proponent agent."""
        transcript_text = self._format_transcript(transcript)
        
        messages: List[LLMMessage] = [
            SystemMessage(content=PROPONENT_PROMPT),
            UserMessage(
                content=f"Task: {task.get('description', '')}\n\nDebate so far:\n{transcript_text}\n\nPresent your argument.",
                source="user",
            ),
        ]
        
        return await super()._get_llm_response(self._model_client, messages, self._max_retries)
    
    async def _run_opponent(
        self,
        task: Dict[str, Any],
        transcript: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Run opponent agent."""
        transcript_text = self._format_transcript(transcript)
        
        messages: List[LLMMessage] = [
            SystemMessage(content=OPPONENT_PROMPT),
            UserMessage(
                content=f"Task: {task.get('description', '')}\n\nDebate so far:\n{transcript_text}\n\nPresent your counterargument.",
                source="user",
            ),
        ]
        
        return await super()._get_llm_response(self._model_client, messages, self._max_retries)
    
    async def _run_judge(
        self,
        task: Dict[str, Any],
        transcript: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Run judge agent."""
        transcript_text = self._format_transcript(transcript)
        
        messages: List[LLMMessage] = [
            SystemMessage(content=JUDGE_PROMPT),
            UserMessage(
                content=f"Task: {task.get('description', '')}\n\nComplete Debate:\n{transcript_text}\n\nEvaluate and determine the best approach.",
                source="user",
            ),
        ]
        
        return await super()._get_llm_response(self._model_client, messages, self._max_retries)
    
    async def _run_executor(
        self,
        task: Dict[str, Any],
        judgment: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> int:
        """Run executor to implement the chosen approach."""
        # Combine tool info from system_prompt with executor instructions
        executor_system = self._system_prompt + "\n\n" + EXECUTOR_PROMPT if self._system_prompt else EXECUTOR_PROMPT
        
        # Include full task context for executor
        task_prompt = self._format_task_prompt(task)
        
        messages: List[LLMMessage] = [
            SystemMessage(content=executor_system),
            UserMessage(
                content=f"{task_prompt}\n\nChosen Approach:\n{judgment.get('final_approach', '')}\n\nExecute this approach using the available tools.",
                source="user",
            ),
        ]
        
        max_turns = self._config.max_turns if hasattr(self._config, 'max_turns') else 20
        turn = 0
        
        while turn < max_turns:
            turn += 1
            response = await super()._get_llm_response(self._model_client, messages, self._max_retries)
            if not response:
                break
            
            action = response.get("action")
            action_input = response.get("action_input", {})
            thought = response.get("thought", "")
            
            self._log_reasoning("executor", thought)
            
            if action == "finish":
                break
            
            observation = await self._execute_action(action, action_input)
            self._log_action(action, action_input, observation)
            
            # Check for session errors
            if isinstance(observation, dict):
                error_type = observation.get("error")
                if error_type in ["time_limit_exceeded", "turn_limit_exceeded", "session_not_active"]:
                    self._logger.warning(f"Stopping execution due to session error: {error_type}")
                    break
            
            messages.append(AssistantMessage(content=json.dumps(response), source="assistant"))
            messages.append(UserMessage(content=f"OBSERVATION: {json.dumps(observation)}", source="user"))
        
        return turn
    
    def _format_transcript(self, transcript: List[Dict[str, Any]]) -> str:
        """Format debate transcript for display."""
        if not transcript:
            return "(No debate yet)"
        
        lines = []
        for entry in transcript:
            role = entry.get("role", "unknown").upper()
            round_num = entry.get("round", "?")
            argument = entry.get("argument", "")
            lines.append(f"[{role} - Round {round_num}]: {argument}")
        
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
    
    def _format_task_prompt(self, task: Dict[str, Any]) -> str:
        """Format the task as a prompt for the LLM."""
        context = task.get("context", {})
        context_str = json.dumps(context, indent=2) if context else "{}"
        return f"""Task ID: {task.get('task_id', 'unknown')}
Description: {task.get('description', '')}

Context:
{context_str}
"""
