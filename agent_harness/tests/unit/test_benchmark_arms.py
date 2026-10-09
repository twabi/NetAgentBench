"""Unit tests for the property-guidance experiment arms."""

from dagent.benchmark.arms import (
    arm_shows_properties,
    build_benchmark_instructions,
    build_task_context,
    normalize_arm,
)

DECLARED = "IMPORTANT: You are configuring network devices to satisfy specific properties."

TASK = {
    "task_id": "guide_ospf_multiarea",
    "description": "Deploy multi-area OSPF ...",
    "intent": {"properties": [{"id": "area0_adjacency"}]},
    "properties": [{"id": "area0_adjacency"}],
    "optimal_solution": {"command_count": 40},
}


def test_normalize_arm_defaults_to_declared():
    assert normalize_arm(None) == "declared"
    assert normalize_arm("  FEEDBACK ") == "feedback"


def test_only_blind_hides_properties():
    assert arm_shows_properties("blind") is False
    for arm in ("declared", "feedback", "placebo", None):
        assert arm_shows_properties(arm) is True


def test_blind_context_strips_declared_criteria():
    ctx = build_task_context(TASK, "blind")
    assert "intent" not in ctx
    assert "properties" not in ctx
    assert ctx["description"] == TASK["description"]
    assert "intent" in TASK


def test_non_blind_context_keeps_properties():
    for arm in ("declared", "feedback", "placebo"):
        ctx = build_task_context(TASK, arm)
        assert ctx["intent"]["properties"][0]["id"] == "area0_adjacency"
        assert ctx["properties"][0]["id"] == "area0_adjacency"


def test_every_arm_drops_the_answer_key():
    task = {
        **TASK,
        "preconfiguration": [{"node": "R2", "command": "router ospf"}],
        "topology": {"nodes": [{"name": "R1"}]},
        "intent": {
            "properties": [
                {
                    "id": "area0_adjacency",
                    "description": "R1 and R2 are adjacent in area 0",
                    "evaluation": {
                        "command": "show ip ospf neighbor",
                        "success_condition": {"contains_text": "Full/"},
                    },
                }
            ]
        },
    }
    for arm in ("declared", "feedback", "placebo", "blind"):
        ctx = build_task_context(task, arm)
        assert "preconfiguration" not in ctx
        assert "optimal_solution" not in ctx
        if arm != "blind":
            prop = ctx["intent"]["properties"][0]
            assert prop["id"] == "area0_adjacency"
            assert prop["description"] == "R1 and R2 are adjacent in area 0"
            assert "evaluation" not in prop
        assert task["preconfiguration"][0]["node"] == "R2"


def test_blind_instructions_are_property_neutral():
    text = build_benchmark_instructions("blind", DECLARED)
    assert "satisfy specific properties" not in text
    assert "NOT" in text  # explicitly tells the agent it has no success criteria


def test_declared_instructions_unchanged():
    assert build_benchmark_instructions("declared", DECLARED) == DECLARED
    assert build_benchmark_instructions(None, DECLARED) == DECLARED


def test_feedback_adds_check_properties_note():
    text = build_benchmark_instructions("feedback", DECLARED)
    assert DECLARED in text
    assert "check_properties" in text
    assert "check_syntactic_validity" not in text


def test_placebo_adds_syntactic_note():
    text = build_benchmark_instructions("placebo", DECLARED)
    assert DECLARED in text
    assert "check_syntactic_validity" in text
