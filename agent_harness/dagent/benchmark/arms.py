"""Property-guidance experiment arms for the dagent benchmark runner.

The four-arm ablation (blind / declared / feedback / placebo) manipulates ONLY:
  1. whether the agent is shown the declared intent properties (success criteria), and
  2. which on-request progress-check tool it is told to use.

Everything else (topology, task description, model, budget) is held constant so
that arm differences isolate the effect of the declared property contract.
"""

import copy
from typing import Any, Dict, Optional

BLIND_ARMS = {"blind"}


def normalize_arm(feedback_arm: Optional[str]) -> str:
    """Normalize an arm label; default to 'declared' when unset."""
    return (feedback_arm or "declared").strip().lower()


def arm_shows_properties(feedback_arm: Optional[str]) -> bool:
    """Blind is the only arm that hides the declared intent properties."""
    return normalize_arm(feedback_arm) not in BLIND_ARMS


def _property_without_checker(prop: Any) -> Any:
    """Keep the property id and description. Drop the match command and regex."""
    if not isinstance(prop, dict):
        return prop
    return {key: value for key, value in prop.items() if key != "evaluation"}


def _strip_answer_key(task_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Remove the injected fault, the reference solution, and property checkers."""
    context = copy.deepcopy(task_dict)
    context.pop("preconfiguration", None)
    context.pop("optimal_solution", None)
    intent = context.get("intent")
    if isinstance(intent, dict) and isinstance(intent.get("properties"), list):
        intent["properties"] = [_property_without_checker(prop) for prop in intent["properties"]]
    if isinstance(context.get("properties"), list):
        context["properties"] = [_property_without_checker(prop) for prop in context["properties"]]
    return context


def build_task_context(
    task_dict: Dict[str, Any], feedback_arm: Optional[str]
) -> Dict[str, Any]:
    """Return the task context the agent should see for this arm.

    Every arm loses preconfiguration, optimal_solution, and property evaluation
    checkers. The blind arm also loses the declared intent properties, so the
    agent pursues the natural-language goal without machine-checkable criteria.
    """
    context = _strip_answer_key(task_dict)
    if arm_shows_properties(feedback_arm):
        return context
    context.pop("intent", None)
    context.pop("properties", None)
    return context


_BLIND_INSTRUCTIONS = """
IMPORTANT: You are configuring network devices to accomplish the task described above.

You are given a natural-language description of the desired network. You are NOT
given an explicit list of machine-checkable success criteria. Use standard network
engineering practice to decide what "done" means, and verify your own work with
show/ping commands before finishing.

1. Design a coherent IP addressing scheme consistent with the task description.
   - Loopbacks: 10.0.0.X/32; point-to-point links: /30 or /31 subnets; keep it consistent.

2. Platform-specific commands:
   - FRR routers: use vtysh (e.g. `vtysh -c "configure terminal" -c "interface eth1" -c "ip address 10.1.0.1/30"`) or Linux `ip` commands.
   - OSPF/BGP: configure via vtysh.
   - Enable forwarding when needed: `sysctl -w net.ipv4.ip_forward=1`.

CRITICAL ERROR HANDLING RULES:
After EVERY command, inspect the OBSERVATION:
1. Check the 'success' field FIRST. If False, the command FAILED: acknowledge it,
   diagnose via stdout/stderr/exit_code, fix the error, and retry. Do not proceed
   as if it worked.
2. If 'success' is True but stdout is empty when you expected output, something is
   wrong; do not claim success.
3. NEVER hallucinate success. Base every thought on the ACTUAL observation.

Before finishing, run verification commands (show/ping) to confirm the network
behaves as described. Only then call the 'submit' tool.
"""


_FEEDBACK_TOOL_NOTE = """

PROGRESS CHECK TOOL (REQUIRED):
A tool named `check_properties` (action: "check_properties", no arguments) is
available. Calling it returns the live satisfaction status of the declared intent
properties evaluated on the CURRENT network state, including which properties are
not yet satisfied. You MUST use it as follows:
- Call `check_properties` after your initial configuration to see what is missing.
- Iterate: fix unsatisfied properties, then call `check_properties` again.
- You MUST call `check_properties` at least once and confirm all properties are
  satisfied BEFORE you call `submit`.
Do not rely on assumptions; use the tool to verify progress.
"""


_PLACEBO_TOOL_NOTE = """

PROGRESS CHECK TOOL (REQUIRED):
A tool named `check_syntactic_validity` (action: "check_syntactic_validity", no
arguments) is available. Calling it reports whether your recent commands executed
successfully (command success rate) on the current session. You MUST call
`check_syntactic_validity` at least once to review your command success rate
BEFORE you call `submit`.
"""


def build_benchmark_instructions(
    feedback_arm: Optional[str], declared_instructions: str
) -> str:
    """Compose the benchmark instructions for the given arm.

    - blind: property-neutral instructions (no declared criteria).
    - declared: the standard property-centric instructions, unchanged.
    - feedback: declared instructions plus a note to use `check_properties`.
    - placebo: declared instructions plus a note to use `check_syntactic_validity`.
    """
    arm = normalize_arm(feedback_arm)
    if arm in BLIND_ARMS:
        return _BLIND_INSTRUCTIONS
    if arm == "feedback":
        return declared_instructions + _FEEDBACK_TOOL_NOTE
    if arm == "placebo":
        return declared_instructions + _PLACEBO_TOOL_NOTE
    return declared_instructions
