"""
Benchmark agent runner.

Entry point for running benchmark tasks with configured agents.
"""

import json
import logging
import traceback
from pathlib import Path
from typing import Dict, Any

from dagent.core.providers.factory import ModelProviderFactory
from dagent.core.agent.patterns.single import SingleAgentPattern
from dagent.core.agent.patterns.sequential import SequentialPattern
from dagent.core.agent.patterns.concurrent import ConcurrentPattern
from dagent.core.agent.patterns.debate import DebatePattern
from dagent.core.agent.patterns.group_chat import GroupChatPattern
from dagent.core.agent.config import MASConfig
from dagent.benchmark.mcp_client import BenchmarkMCPClient
from dagent.benchmark.config import BenchmarkAgentConfig, AgentMode, AgentStructure

logger = logging.getLogger(__name__)


async def run_benchmark_agent(
    mcp_url: str,
    task_dict: Dict[str, Any],
    agent_config: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Run a benchmark agent on a task.
    
    Args:
        mcp_url: URL of the MCP server
        task_dict: task definition dictionary
        agent_config: agent configuration dictionary
        
    Returns:
        Result dictionary with success status and metrics
    """
    # 1. Load config
    if agent_config:
        # Convert string to Enum if needed
        mode = agent_config.get("mode", AgentMode.SINGLE)
        if isinstance(mode, str):
            try:
                agent_config["mode"] = AgentMode(mode)
            except ValueError:
                return {"success": False, "error": f"Unknown agent mode: {mode}", "turns_used": 0}
                
        structure = agent_config.get("structure", AgentStructure.SEQUENTIAL)
        if isinstance(structure, str):
            try:
                agent_config["structure"] = AgentStructure(structure)
            except ValueError:
                return {"success": False, "error": f"Unknown agent structure: {structure}", "turns_used": 0}
                
        config = BenchmarkAgentConfig(**agent_config)
    else:
        config = BenchmarkAgentConfig()
    
    logger.info(f"Running benchmark with config: mode={config.mode.value}, provider={config.provider}")
    
    # 2. Create model client via provider
    try:
        provider = ModelProviderFactory.create(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
            host=config.host,
            context_length=getattr(config, "context_length", None)
        )
        model_client = provider.create_client()
    except Exception as e:
        logger.error(f"Failed to create model client: {e}")
        return {"success": False, "error": f"Model initialization failed: {str(e)}", "turns_used": 0}
        
    # 3. Create tool executor (MCP client)
    mcp_client = BenchmarkMCPClient(mcp_url)
    try:
        await mcp_client.connect()
    except Exception as e:
        logger.error(f"Failed to connect to MCP: {e}")
        return {"success": False, "error": f"MCP connection failed: {str(e)}", "turns_used": 0}
        
    try:
        # Fetch available tools and update system prompt
        try:
            tools = await mcp_client.list_tools()
            tools_desc = []
            for t in tools:
                schema = json.dumps(t.get('input_schema', {}))
                tools_desc.append(f"- {t['name']}: {t['description']}\n  Schema: {schema}")
            
            tool_prompt = "Available Tools:\n" + "\n".join(tools_desc) if tools_desc else "No tools available."
        except Exception as e:
            logger.warning(f"Failed to fetch tools: {e}")
            tool_prompt = "Failed to fetch tools."

        # Construct system prompt with tools and benchmark-specific instructions
        benchmark_instructions = """
IMPORTANT: You are configuring network devices to satisfy specific properties.

IP ADDRESSING REQUIREMENTS:
1. **Properties are your constraints**: Review ALL properties first to identify required IP addresses
   - If a property tests 'ping 10.3.0.3', then 10.3.0.3 MUST exist in your design
   - If a property checks for 'contains_text: "10.0.0.1"', you MUST configure 10.0.0.1
   - Properties define the REQUIRED IPs - your job is to design a coherent scheme that includes them

2. **Design a coherent IP addressing scheme**:
   - For loopback interfaces: Use 10.0.0.X/32 (where X matches node number or identifier)
   - For point-to-point links: Use /30 or /31 subnets (e.g., 10.X.0.1/30 and 10.X.0.2/30)
   - For shared segments: Use appropriate subnet masks (/24 for small networks)
   - Maintain consistency across your design

3. **Network design workflow**:
   a) Read the complete task definition (topology + properties)
   b) Extract all required IPs from property success_conditions
   c) Design an IP scheme that satisfies these constraints
   d) Configure interfaces with your planned IPs
   e) Add routing (static routes, OSPF, BGP) as needed
   f) Verify properties are satisfied

4. **Platform-specific commands**:
   - For FRR routers: Can use EITHER vtysh commands OR Linux ip commands
     * vtysh: `vtysh -c "configure terminal" -c "interface eth1" -c "ip address 10.1.0.1/24"`
     * Linux: `ip addr add 10.1.0.1/24 dev eth1`
   - For static routes: `ip route add 10.2.0.0/24 via 10.1.0.1`
   - For OSPF: Must use vtysh with proper OSPF configuration
   - Enable IP forwarding when needed: `sysctl -w net.ipv4.ip_forward=1`

CRITICAL ERROR HANDLING RULES:
After EVERY command, you MUST check the OBSERVATION response:

1. **Check the 'success' field FIRST**:
   - If 'success': False → The command FAILED. Do NOT proceed to the next step!
   - Your next thought MUST acknowledge the failure: "The command failed with error: [error message]"
   - Diagnose WHY it failed by reading 'stdout', 'stderr', and 'exit_code'
   - Fix the error and retry the command with corrections

2. **Verify output contains expected data**:
   - If 'success': True but 'stdout' is empty when you expect output → Something is wrong!
   - Example: "show ip route rip" returns empty stdout → No RIP routes learned yet
   - Do NOT claim "I have verified routes are learned" when stdout is empty

3. **NEVER hallucinate success**:
   - Do NOT say "I have configured X" if the observation shows 'success': False
   - Do NOT say "I have verified Y" if the output doesn't contain the expected data
   - Always base your thoughts on the ACTUAL observation, not what you expect

4. **Examples of CORRECT error handling**:
   
   BAD Response (what NOT to do):
   - Observation: {'success': False, 'stdout': 'Error: command not found'}
   - Thought: "I have successfully configured the interface"  ← WRONG!
   
   GOOD Response:
   - Observation: {'success': False, 'stdout': 'Error: command not found'}
   - Thought: "The command failed because the command is not found. I need to use a different command syntax."
   - Action: [retry with corrected command]

5. **Verification before submit**:
   - Before calling 'submit', run verification commands for EACH property
   - Example: If property checks "ping 10.0.0.4", run that exact ping command
   - Check that the verification output matches the expected success condition
   - Only submit if ALL verifications pass

Remember: A real network engineer would NEVER configure a network without testing it works!
You must verify each step actually succeeded before moving on.

After verifying your solution satisfies all properties, call the 'submit' tool to complete the task.
"""
        system_prompt = f"""You are an AI assistant that solves tasks by executing tool actions.

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanations, no markdown, no text before or after the JSON.

JSON FORMAT (respond with ONLY this, nothing else):
{{
    "thought": "Brief reasoning about what to do next",
    "action": "tool_name",
    "action_input": {{"param1": "value1"}}
}}

To finish the task:
{{
    "thought": "Task complete",
    "action": "finish",
    "action_input": {{}}
}}

RULES:
- Output ONLY the JSON object
- NO markdown code blocks
- NO explanations before or after
- Just the raw JSON object

REMEMBER: You have limited turns and time!
- Call 'get_session_status' BEFORE starting extensive work to check your constraints
- Use this info to plan: if you have 5 turns left, prioritize essential configs over verification
- If time is running low, call 'submit' when the core requirements are met

AVAILABLE TOOLS:
- exec_command: Execute a command on a network node
- get_session_status: Check turns/time remaining (USE THIS for planning!)
- get_nodes: Get list of available nodes
- submit: Complete the task (call when satisfied with your configuration)

{tool_prompt}
{benchmark_instructions}"""
        
        # 4. Create pattern-based config
        mas_config = MASConfig(
            max_turns=task_dict.get("turn_limit", 50),
            context_length=config.context_length,
        )
        
        # 5. Create pattern based on mode
        if config.mode == AgentMode.SINGLE:
            pattern = SingleAgentPattern(
                runtime=None,  # Not using pub/sub
                config=mas_config,
                model_client=model_client,
                tool_executor=mcp_client,
                system_prompt=system_prompt,
            )
        elif config.mode == AgentMode.MULTI:
            if config.structure == AgentStructure.SEQUENTIAL:
                pattern = SequentialPattern(
                    runtime=None,  # Not using pub/sub
                    config=mas_config,
                    model_client=model_client,
                    tool_executor=mcp_client,
                    system_prompt=system_prompt,
                )
            elif config.structure == AgentStructure.CONCURRENT:
                pattern = ConcurrentPattern(
                    runtime=None,  # Not using pub/sub
                    config=mas_config,
                    model_client=model_client,
                    tool_executor=mcp_client,
                    system_prompt=system_prompt,
                )
            elif config.structure == AgentStructure.DEBATE:
                pattern = DebatePattern(
                    runtime=None,
                    config=mas_config,
                    model_client=model_client,
                    tool_executor=mcp_client,
                    system_prompt=system_prompt,
                )
            elif config.structure == AgentStructure.GROUP_CHAT:
                pattern = GroupChatPattern(
                    runtime=None,
                    config=mas_config,
                    model_client=model_client,
                    tool_executor=mcp_client,
                    system_prompt=system_prompt,
                )
            else:
                return {"success": False, "error": f"Unsupported agent structure: {config.structure}", "turns_used": 0}
        else:
            return {"success": False, "error": f"Unknown agent mode: {config.mode}", "turns_used": 0}
            
        # 6. Create task dictionary
        # Pass the ENTIRE task definition as context so models have access to all information:
        # - topology (nodes, links)
        # - properties (requirements with success conditions)
        # - optimal_solution (hints about expected approach)
        # - research_context (complexity estimates)
        # This eliminates the need for prompt engineering and ensures consistent information access.
        
        task = {
            "task_id": task_dict["task_id"],
            "description": task_dict["description"],
            "context": task_dict,  # Pass complete task definition
            "turn_limit": task_dict.get("turn_limit", 50),
            "time_limit": task_dict.get("time_limit", 600.0),
        }
        
        # 7. Run pattern
        result = await pattern.execute(task)
        
        # 8. Format result
        return {
            "success": result.get("success", False),
            "turns_used": result.get("turns_used", 0),
            "actions_executed": result.get("actions_executed", []),
            "reasoning_trace": result.get("reasoning_trace", []),
            "error": result.get("error"),
            # New tracking metrics
            "token_usage": result.get("token_usage", {}),
            "tool_usage": result.get("tool_usage", {}),
            "agent_conversations": result.get("agent_conversations", []),
        }
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        tb_str = traceback.format_exc()
        logger.error(f"Traceback:\n{tb_str}")
        # Also write to a dedicated file for easy inspection.
        error_log = Path.cwd() / "execution_error.log"
        with open(error_log, "w") as f:
            f.write(f"Error: {str(e)}\n\nTraceback:\n{tb_str}")
            
        return {"success": False, "error": f"Execution failed: {str(e)}", "turns_used": 0}
        
    finally:
        await mcp_client.disconnect()
