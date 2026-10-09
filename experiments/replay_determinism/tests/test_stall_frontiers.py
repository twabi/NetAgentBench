"""Stall frontiers use original terminal property vectors (Table 1 clock)."""

from collections import Counter

from plot_rq3_figures import TASK_PREREQ_ORDER, stall_frontier_counts


def _run(task_id: str, satisfied: list[str]) -> dict:
    return {"task_id": task_id, "original_satisfied": satisfied}


def test_rip_stall_matches_terminal_complete_and_routes():
    runs = (
        [_run("ccna_rip_routing_basic", [
            "rip_process_running",
            "ripv2_configured",
            "rip_routes_learned",
            "full_reachability",
        ])]
        * 11
        + [_run("ccna_rip_routing_basic", [
            "rip_process_running",
            "ripv2_configured",
        ])]
        * 3
    )
    counts = stall_frontier_counts(runs)
    assert counts["ccna_rip_routing_basic"] == Counter(
        {"Fully Achieved": 11, "RIP routes": 3}
    )


def test_ospf_ts_stall_uses_first_unsatisfied_in_chain():
    runs = [
        _run(
            "troubleshoot_ospf_adjacency_issue",
            [
                "initial_problem_identified",
                "root_cause_diagnosed",
                "adjacency_restored",
                "full_topology_convergence",
            ],
        ),
        _run(
            "troubleshoot_ospf_adjacency_issue",
            [
                "initial_problem_identified",
                "root_cause_diagnosed",
                "adjacency_restored",
            ],
        ),
        _run(
            "troubleshoot_ospf_adjacency_issue",
            ["initial_problem_identified", "root_cause_diagnosed"],
        ),
        _run(
            "troubleshoot_ospf_adjacency_issue",
            ["initial_problem_identified"],
        ),
    ]
    counts = stall_frontier_counts(runs)
    assert counts["troubleshoot_ospf_adjacency_issue"] == Counter(
        {
            "Fully Achieved": 1,
            "OSPF TS conv.": 1,
            "OSPF TS adj.": 1,
            "OSPF TS diag.": 1,
        }
    )


def test_ignores_tasks_without_prerequisite_chain():
    runs = [_run("troubleshoot_bgp_route_filtering", ["filtering_verified"])]
    assert stall_frontier_counts(runs) == {}
    assert "troubleshoot_bgp_route_filtering" not in TASK_PREREQ_ORDER
