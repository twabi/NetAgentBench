"""Prompt and task-context builders for property-guidance arms."""

from __future__ import annotations

import copy
import json
from typing import Any

from benchmark.guide.arms import FeedbackArm


def format_declared_properties_block(properties: list[dict[str, Any]]) -> str:
    lines = [
        "Intent properties (fixed before you act). You succeed when all are satisfied on live network state:",
    ]
    for prop in properties:
        lines.append(f"- {prop['id']}: {prop['description']}")
    return "\n".join(lines)


def sanitize_task_context_for_arm(
    task_dict: dict[str, Any],
    arm: FeedbackArm,
) -> dict[str, Any]:
    """Return a copy of the task dict appropriate for the agent-facing context."""
    ctx = copy.deepcopy(task_dict)
    intent = ctx.get("intent") or {}
    props = intent.get("properties") or []

    if arm == FeedbackArm.BLIND:
        ctx.pop("intent", None)
        ctx.pop("fault_verification", None)
        return ctx

    declared = [
        {"id": p["id"], "description": p["description"], "type": p.get("type")}
        for p in props
    ]
    ctx["intent"] = {"properties": declared}
    ctx.pop("fault_verification", None)
    return ctx


def build_benchmark_instructions(arm: FeedbackArm) -> str:
    if arm == FeedbackArm.BLIND:
        return """
IMPORTANT: Configure the network to satisfy the task description.

IP ADDRESSING:
- Design a coherent scheme from the topology and description
- For FRR: use vtysh or Linux ip commands as appropriate
- Enable IP forwarding when needed: sysctl -w net.ipv4.ip_forward=1

ERROR HANDLING:
- Check the 'success' field in every OBSERVATION before proceeding
- Do not claim success when a command failed
- Verify connectivity with read commands before submit

After verifying your configuration, call 'submit'.
"""

    base = """
IMPORTANT: Configure the network to satisfy the declared intent properties.

IP ADDRESSING:
- Properties define required outcomes; design addressing to support them
- For FRR: use vtysh or Linux ip commands as appropriate

ERROR HANDLING:
- Check the 'success' field in every OBSERVATION before proceeding
- Do not claim a property is satisfied without evidence from read commands

Before submit, ensure the live network state would satisfy every intent property.
"""

    if arm == FeedbackArm.FEEDBACK:
        return base + """
PROPERTY FEEDBACK:
- You may call 'check_properties' (no config turn consumed) to get live eval(s, P)
- The reply lists each property id and whether it is currently satisfied, plus completeness
- Use this to verify progress; do not call it excessively (cap applies)
"""

    if arm == FeedbackArm.PLACEBO:
        return base + """
SYNTACTIC CHECK:
- You may call 'check_syntactic_validity' (no config turn consumed) for command success rate
- This reports whether recent commands executed without error; it is NOT property satisfaction
"""

    return base


def build_system_prompt(
    arm: FeedbackArm,
    tool_prompt: str,
    properties: list[dict[str, Any]] | None = None,
) -> str:
    declared_block = ""
    if arm != FeedbackArm.BLIND and properties:
        declared_block = "\n\n" + format_declared_properties_block(properties)

    tool_lines = [
        "- exec_command: Execute a command on a network node",
        "- get_session_status: Check turns/time remaining",
        "- get_nodes: Get list of available nodes",
        "- submit: Complete the task",
    ]
    if arm == FeedbackArm.FEEDBACK:
        tool_lines.append(
            "- check_properties: Live eval of declared intent properties (read-only, no turn)"
        )
    elif arm == FeedbackArm.PLACEBO:
        tool_lines.append(
            "- check_syntactic_validity: Recent command success rate (read-only, no turn)"
        )

    static_tools = "AVAILABLE TOOLS:\n" + "\n".join(tool_lines)

    return f"""You are an AI assistant that solves tasks by executing tool actions.

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanations, no markdown.

JSON FORMAT:
{{
    "thought": "Brief reasoning about what to do next",
    "action": "tool_name",
    "action_input": {{"param1": "value1"}}
}}

To finish:
{{
    "thought": "Task complete",
    "action": "finish",
    "action_input": {{}}
}}

RULES:
- Output ONLY the JSON object
- Call 'get_session_status' early to plan your turn budget

{static_tools}

{tool_prompt}
{build_benchmark_instructions(arm)}{declared_block}"""


def format_task_user_message(task: dict[str, Any], arm: FeedbackArm) -> str:
    """Build the user message for SingleAgentPattern (arm-aware)."""
    context = task.get("context", {})
    if arm == FeedbackArm.BLIND:
        instructions = [
            "1. Review the topology and description",
            "2. Configure the network to meet the task goal",
            "3. Verify with read commands, then call 'submit'",
        ]
    else:
        instructions = [
            "1. Review the topology and declared intent properties (ids and descriptions only)",
            "2. Configure the network so each property would be satisfied on live state",
            "3. Verify with read commands",
            "4. Call 'submit' when done",
        ]
        if arm == FeedbackArm.FEEDBACK:
            instructions.insert(3, "3b. Use 'check_properties' to query live property satisfaction")
        elif arm == FeedbackArm.PLACEBO:
            instructions.insert(
                3, "3b. You may use 'check_syntactic_validity' for command success rate"
            )

    return "\n".join(
        [
            f"Task ID: {task.get('task_id', 'unknown')}",
            f"Description: {task.get('description', '')}",
            "",
            "=" * 60,
            "TASK CONTEXT:",
            "=" * 60,
            json.dumps(context, indent=2),
            "",
            "=" * 60,
            "INSTRUCTIONS:",
            "=" * 60,
            *[f"{i}. {line.split('. ', 1)[-1]}" for i, line in enumerate(instructions, 1)],
        ]
    )
