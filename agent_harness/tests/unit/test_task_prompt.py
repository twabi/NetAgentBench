"""The benchmark prompt states the goal and the topology, not the checkers."""

from dagent.core.agent.patterns.single import SingleAgentPattern


def test_prompt_states_the_goal_and_hides_properties():
    task = {
        "task_id": "troubleshoot_bgp_route_filtering",
        "description": "The ISP learns only 192.0.2.0/24 from the edge.",
        "context": {
            "description": "The ISP learns only 192.0.2.0/24 from the edge.",
            "topology": {"nodes": [{"name": "EDGE"}], "links": []},
            "intent": {
                "properties": [
                    {
                        "id": "filter_applied_outbound",
                        "description": "Apply route-map FILTER-OUT outbound",
                        "evaluation": {"command": "show ip bgp", "success_condition": {"pattern": "FILTER-OUT"}},
                    }
                ]
            },
            "properties": [{"id": "filter_applied_outbound"}],
            "preconfiguration": [{"node": "EDGE", "command": "route-map FILTER-OUT"}],
            "optimal_solution": {"description": "attach FILTER-OUT"},
            "research_context": {"citation": "The injected fault is an unattached route-map."},
            "fault_verification": [{"id": "verify_internal_leak"}],
        },
    }
    prompt = SingleAgentPattern._format_task_prompt(None, task)
    assert "The ISP learns only 192.0.2.0/24 from the edge." in prompt
    assert '"name": "EDGE"' in prompt
    for hidden in (
        "filter_applied_outbound",
        "FILTER-OUT",
        "preconfiguration",
        "optimal_solution",
        "research_context",
        "fault_verification",
        "intent",
        "success_condition",
    ):
        assert hidden not in prompt
