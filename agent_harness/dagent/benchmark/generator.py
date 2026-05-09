"""
Benchmark Configuration Generator.

Provides functionality for one-shot generation of network configurations
without the overhead of an interactive agent loop.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from autogen_core.models import (
    SystemMessage,
    UserMessage,
)

from dagent.core.providers.factory import ModelProviderFactory
from dagent.benchmark.config import BenchmarkAgentConfig

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_FRR = """You are an expert Network Engineer.
Your task is to generate configuration commands for FRR (Free Range Routing) network devices.

CRITICAL: Each requirement shows the EXACT values you MUST use.
For example, if a requirement says "must contain '192.168.1.1'", you MUST configure that exact IP address.

OUTPUT FORMAT:
You must output a VALID JSON object with the following structure:
{
    "nodes": {
        "node_name_1": ["command1", "command2", ...],
        "node_name_2": ["command1", "command2", ...]
    }
}

COMMAND FORMAT RULES FOR FRR:
- Each command should be a simple configuration line (e.g., "interface eth1", "ip address 10.0.1.1/24")
- Do NOT include "vtysh" or "vtysh -c" - commands will be piped to vtysh automatically
- Do NOT include "configure terminal" - it will be added automatically
- For static routes use: "ip route DEST_NETWORK NEXT_HOP" (e.g., "ip route 192.168.1.1/32 10.0.1.2")

ROUTING RULES FOR LINEAR TOPOLOGIES:
For a linear chain like R1--R2--R3--R4--...--Rn:
1. EVERY router needs routes to reach the destination subnet
2. Use the NEXT HOP IP (the adjacent router's interface IP on the shared link)

IP ADDRESSING SCHEME:
- Link between Ri and Ri+1: Use subnet 10.0.i.0/24
  - Ri uses 10.0.i.1 on its downstream interface
  - Ri+1 uses 10.0.i.2 on its upstream interface (eth1)

RULES:
1. Return ONLY the JSON object. No markdown, no explanations.
2. For reachability tasks: configure the exact target IP on the destination node's loopback interface.
3. EVERY router in the path needs a static route to the destination!
"""

SYSTEM_PROMPT_LINUX = """You are an expert Network Engineer.
Your task is to generate Linux shell commands to configure network connectivity on Alpine/Ubuntu nodes.

CRITICAL: Each requirement shows the EXACT values you MUST use.

OUTPUT FORMAT:
You must output a VALID JSON object with the following structure:
{
    "nodes": {
        "node_name_1": ["command1", "command2", ...],
        "node_name_2": ["command1", "command2", ...]
    }
}

COMMAND FORMAT RULES FOR LINUX:
- Use standard Linux iproute2 commands
- IP address: "ip addr add 10.0.1.1/24 dev eth1"
- Bring interface up: "ip link set eth1 up"  
- Static route: "ip route add 192.168.1.0/24 via 10.0.1.2"
- Loopback IP: "ip addr add 192.168.1.1/32 dev lo"

EXAMPLE FOR 2-NODE LINEAR (R1 -- R2):
R1 commands: ["ip addr add 10.0.1.1/24 dev eth1", "ip link set eth1 up", "ip route add 192.168.2.1/32 via 10.0.1.2"]
R2 commands: ["ip addr add 10.0.1.2/24 dev eth1", "ip link set eth1 up", "ip addr add 192.168.2.1/32 dev lo"]

IP ADDRESSING SCHEME:
- Link between Ri and Ri+1: Use subnet 10.0.i.0/24
- For reachability to a node, configure the target IP on that node's loopback (lo)

RULES:
1. Return ONLY the JSON object. No markdown, no explanations.
2. Bring up interfaces with "ip link set ethX up"
3. EVERY node in the path needs a static route to the destination!
"""

def get_system_prompt(platform: str) -> str:
    """Get platform-specific system prompt."""
    if platform in ("linux", "alpine", "ubuntu"):
        return SYSTEM_PROMPT_LINUX
    return SYSTEM_PROMPT_FRR


async def generate_benchmark_config(
    task_dict: Dict[str, Any],
    agent_config: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Generate network configuration for a benchmark task (one-shot).
    
    Args:
        task_dict: task definition dictionary
        agent_config: agent configuration dictionary
        
    Returns:
        Result dictionary with generated commands
    """
    # 1. Load config
    if agent_config:
        config = BenchmarkAgentConfig.from_dict(agent_config)
    else:
        config = BenchmarkAgentConfig()
    
    logger.info(f"Generating config with: provider={config.provider}, model={config.model}, mode={config.mode.value}")
    
    # 2. Create model client
    try:
        provider = ModelProviderFactory.create(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
            host=config.host
        )
        model_client = provider.create_client()
    except Exception as e:
        logger.error(f"Failed to create model client: {e}")
        return {"success": False, "error": f"Model initialization failed: {str(e)}"}

    # 3. Dispatch based on mode
    from dagent.benchmark.config import AgentMode
    
    if config.mode == AgentMode.SINGLE:
        # Single agent: one LLM call
        return await _generate_single_agent(task_dict, model_client, config)
    else:
        # Multi-agent: use pattern-based generation
        return await _generate_multi_agent(task_dict, model_client, config)


async def _generate_single_agent(
    task_dict: Dict[str, Any],
    model_client: Any,
    config: BenchmarkAgentConfig,
) -> Dict[str, Any]:
    """Generate config using a single LLM call."""
    platform = task_dict.get("platform", "frr")
    system_prompt = get_system_prompt(platform)
    task_prompt = _format_task_prompt(task_dict)
    
    messages = [
        SystemMessage(content=system_prompt),
        UserMessage(content=task_prompt, source="user")
    ]
    
    try:
        result = await model_client.create(messages)
        content = result.content
        
        # Handle different response types
        if isinstance(content, str):
            text = content
        elif isinstance(content, list) and len(content) > 0:
            text = content[0].text if hasattr(content[0], 'text') else str(content[0])
        else:
            text = str(content)
        
        logger.debug(f"LLM raw response (first 500 chars): {text[:500]}")
            
        # Parse JSON
        parsed = _extract_json(text)
        if not parsed:
            logger.error(f"Failed to parse JSON from response: {text[:1000]}")
            return {
                "success": False, 
                "error": "Failed to parse JSON from LLM response",
                "raw_response": text
            }
        
        logger.debug(f"Parsed JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
            
        # Convert node-based dict to list of actions
        actions = _parse_config_to_actions(parsed)
        
        logger.info(f"Generated {len(actions)} actions from LLM response")
        
        return {
            "success": True,
            "actions": actions,
            "model_version": f"{config.provider}:{config.model or 'default'}"
        }

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return {"success": False, "error": f"Generation failed: {str(e)}"}


async def _generate_multi_agent(
    task_dict: Dict[str, Any],
    model_client: Any,
    config: BenchmarkAgentConfig,
) -> Dict[str, Any]:
    """
    Generate config using multi-agent pattern.
    
    For one-shot generation, we use a Planner → Verifier pattern:
    1. Planner generates initial config
    2. Verifier reviews and suggests improvements
    3. Planner refines if needed
    """
    from dagent.benchmark.config import AgentStructure
    
    platform = task_dict.get("platform", "frr")
    system_prompt = get_system_prompt(platform)
    task_prompt = _format_task_prompt(task_dict)
    
    # Different behavior based on structure
    if config.structure == AgentStructure.SEQUENTIAL:
        # Planner → Verifier → (optional refinement)
        return await _generate_with_verification(task_dict, model_client, config, system_prompt, task_prompt)
    elif config.structure == AgentStructure.DEBATE:
        # Two proposers debate, then merge best ideas
        return await _generate_with_debate(task_dict, model_client, config, system_prompt, task_prompt)
    else:
        # Fallback to single agent for unsupported structures
        logger.warning(f"Structure {config.structure} not supported for one-shot, using single agent")
        return await _generate_single_agent(task_dict, model_client, config)


async def _generate_with_verification(
    task_dict: Dict[str, Any],
    model_client: Any,
    config: BenchmarkAgentConfig,
    system_prompt: str,
    task_prompt: str,
) -> Dict[str, Any]:
    """Generate with Planner → Verifier pattern."""
    import json
    
    # Phase 1: Planner generates config
    planner_messages = [
        SystemMessage(content=system_prompt),
        UserMessage(content=task_prompt, source="user")
    ]
    
    try:
        result = await model_client.create(planner_messages)
        planner_text = result.content if isinstance(result.content, str) else str(result.content)
        planner_config = _extract_json(planner_text)
        
        if not planner_config:
            return {"success": False, "error": "Planner failed to generate valid config"}
        
        # Phase 2: Verifier reviews
        verifier_prompt = f"""You are a Network Configuration Verifier.
Review this proposed configuration and check for:
1. Missing static routes for reachability
2. Incorrect IP addresses (must match requirements)
3. Missing interface configurations

PROPOSED CONFIG:
{json.dumps(planner_config, indent=2)}

ORIGINAL REQUIREMENTS:
{task_prompt}

If the config is correct, respond with:
{{"verdict": "approved", "config": <original config>}}

If improvements are needed, respond with:
{{"verdict": "improved", "config": <improved config>, "changes": ["list of changes made"]}}

Return ONLY valid JSON."""

        verifier_messages = [
            SystemMessage(content="You are a thorough network configuration reviewer."),
            UserMessage(content=verifier_prompt, source="user")
        ]
        
        result = await model_client.create(verifier_messages)
        verifier_text = result.content if isinstance(result.content, str) else str(result.content)
        verifier_response = _extract_json(verifier_text)
        
        if verifier_response and "config" in verifier_response:
            final_config = verifier_response["config"]
            verdict = verifier_response.get("verdict", "unknown")
            logger.info(f"Verifier verdict: {verdict}")
        else:
            # Use planner config if verifier fails
            final_config = planner_config
            logger.warning("Verifier response invalid, using planner config")
        
        actions = _parse_config_to_actions(final_config)
        
        return {
            "success": True,
            "actions": actions,
            "model_version": f"{config.provider}:{config.model or 'default'}",
            "turns_used": 2,  # Planner + Verifier
        }
        
    except Exception as e:
        logger.error(f"Multi-agent generation failed: {e}")
        return {"success": False, "error": f"Multi-agent generation failed: {str(e)}"}


async def _generate_with_debate(
    task_dict: Dict[str, Any],
    model_client: Any,
    config: BenchmarkAgentConfig,
    system_prompt: str,
    task_prompt: str,
) -> Dict[str, Any]:
    """Generate with Debate pattern - two proposers, then judge picks best."""
    import json
    
    # Phase 1: First proposer
    proposer1_messages = [
        SystemMessage(content=system_prompt + "\n\nYou are Proposer A. Be thorough with static routes."),
        UserMessage(content=task_prompt, source="user")
    ]
    
    try:
        result1 = await model_client.create(proposer1_messages)
        text1 = result1.content if isinstance(result1.content, str) else str(result1.content)
        config1 = _extract_json(text1)
        
        # Phase 2: Second proposer (different emphasis)
        proposer2_messages = [
            SystemMessage(content=system_prompt + "\n\nYou are Proposer B. Focus on minimal, correct configs."),
            UserMessage(content=task_prompt, source="user")
        ]
        
        result2 = await model_client.create(proposer2_messages)
        text2 = result2.content if isinstance(result2.content, str) else str(result2.content)
        config2 = _extract_json(text2)
        
        if not config1 and not config2:
            return {"success": False, "error": "Both proposers failed to generate config"}
        
        # If only one succeeded, use it
        if not config1:
            final_config = config2
        elif not config2:
            final_config = config1
        else:
            # Phase 3: Judge picks best
            judge_prompt = f"""You are a Network Configuration Judge.
Compare these two proposed configurations and select the BETTER one.

PROPOSAL A:
{json.dumps(config1, indent=2)}

PROPOSAL B:
{json.dumps(config2, indent=2)}

REQUIREMENTS:
{task_prompt}

Respond with:
{{"winner": "A" or "B", "reason": "why this one is better", "config": <winning config>}}

Return ONLY valid JSON."""

            judge_messages = [
                SystemMessage(content="You are an expert judge of network configurations."),
                UserMessage(content=judge_prompt, source="user")
            ]
            
            result = await model_client.create(judge_messages)
            judge_text = result.content if isinstance(result.content, str) else str(result.content)
            judge_response = _extract_json(judge_text)
            
            if judge_response and "config" in judge_response:
                final_config = judge_response["config"]
                logger.info(f"Judge picked: {judge_response.get('winner')}, reason: {judge_response.get('reason', 'N/A')[:100]}")
            else:
                # Default to first proposer
                final_config = config1
                logger.warning("Judge response invalid, using Proposal A")
        
        actions = _parse_config_to_actions(final_config)
        
        return {
            "success": True,
            "actions": actions,
            "model_version": f"{config.provider}:{config.model or 'default'}",
            "turns_used": 3,  # 2 proposers + judge
        }
        
    except Exception as e:
        logger.error(f"Debate generation failed: {e}")
        return {"success": False, "error": f"Debate generation failed: {str(e)}"}


def _parse_config_to_actions(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert parsed config JSON to list of actions."""
    actions = []
    if "nodes" in parsed:
        for node, commands in parsed["nodes"].items():
            if isinstance(commands, list):
                for cmd in commands:
                    actions.append({
                        "action": "exec_command",
                        "input": {
                            "node": node,
                            "command": cmd
                        }
                    })
    return actions


def _format_task_prompt(task_dict: Dict[str, Any]) -> str:
    """Format the task dictionary into a readable prompt."""
    
    # Extract explicit requirements and target IPs
    requirements = []
    target_ips = []  # (destination_node, target_ip) tuples
    
    for prop in task_dict.get("properties", []):
        desc = prop.get("description", "")
        evaluation = prop.get("evaluation", {})
        success = evaluation.get("success_condition", {})
        
        # Format requirements like multi-turn mode does
        if "contains_text" in success:
            req_str = f"- {desc}: must contain '{success['contains_text']}'"
        elif "json_path" in success:
            req_str = f"- {desc}: must match {success['json_path']} == {success.get('expected_value')}"
        else:
            req_str = f"- {desc}"
             
        requirements.append(req_str)
        
        # Extract target IP from ping command (e.g., "ping -c 3 192.168.10.10")
        cmd = evaluation.get("command", "")
        if "ping" in cmd:
            # Extract IP address from ping command
            parts = cmd.split()
            for part in parts:
                if re.match(r'\d+\.\d+\.\d+\.\d+', part):
                    # Find which node is being reached (from description like "R1 can reach R10")
                    # Description format: "R1 can reach R10 via ping" - destination is before "via" or at end
                    if " reach " in desc:
                        dest_part = desc.split(" reach ")[1].split()[0]  # Get "R10" from "R10 via ping"
                        target_ips.append((dest_part, part))
                    break

    platform = task_dict.get("platform", "frr")
    
    # Format topology links
    links = task_dict.get("links", [])
    topology_info = []
    if links:
        topology_info.append("Links (interface connections):")
        for link in links:
            endpoints = link.get("endpoints", [])
            if len(endpoints) == 2:
                topology_info.append(f"  - {endpoints[0]} <-> {endpoints[1]}")
    else:
        topology_info.append("Links: Not specified - configure interfaces as appropriate")
    
    # Format target IP requirements
    target_ip_info = ""
    if target_ips:
        target_ip_info = "\n\nCRITICAL: The following IPs MUST be configured on these nodes:\n"
        for dest_node, target_ip in target_ips:
            target_ip_info += f"  - {dest_node} MUST have IP address {target_ip} on its loopback (lo) interface\n"
        target_ip_info += "These are the IPs that will be pinged to verify reachability!\n"
    
    return f"""
Network Configuration Task
==========================
Platform: {platform}
Task ID: {task_dict.get('task_id')}
Description: {task_dict.get('description')}

Topology:
Nodes: {', '.join(task_dict.get('nodes', []))}
{chr(10).join(topology_info)}

Requirements:
{chr(10).join(requirements)}
{target_ip_info}
Instructions:
1. Configure IP addresses on the specified interfaces to enable connectivity between adjacent nodes.
2. For point-to-point links, use separate /24 subnets (e.g., 10.0.1.0/24 for link 1, 10.0.2.0/24 for link 2).
3. If a node needs to be reachable at a specific IP (see CRITICAL section above), configure that IP on its loopback interface.
4. For reachability between non-adjacent nodes, add STATIC ROUTES on EVERY router in the path.
5. Return the commands in the JSON format specified in the system prompt.
"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from text."""
    # Remove <think>...</think> blocks (DeepSeek R1 style)
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    try:
        # 1. Try direct parse
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass
        
    # 2. Try to find ```json code block (first match)
    match = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
            
    # 3. Try to extract the first complete JSON object using brace balancing
    start = clean_text.find('{')
    if start >= 0:
        depth = 0
        in_string = False
        escape_next = False
        for i, char in enumerate(clean_text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(clean_text[start:i+1])
                    except json.JSONDecodeError:
                        break
            
    return None
