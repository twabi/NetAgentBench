import pytest
from unittest.mock import MagicMock, patch
from benchmark.interactive_controller import InteractiveBenchmarkController
from benchmark.models.task import TaskDefinition, IntentSpecification, TopologySpecification, Property, PropertyType, EvaluationProcedure, Node, NodeType, Platform
from benchmark.models.results import PropertyEvaluationResult, ScoringResult, ValidityCheck, ExecutionMetrics

@pytest.fixture
def mock_task():
    return TaskDefinition(
        task_id="test_task",
        description="test",
        platform="frr",
        intent=IntentSpecification(properties=[
            Property(
                id="p1", 
                description="test prop", 
                type=PropertyType.REACHABILITY, 
                evaluation=EvaluationProcedure(
                    method="exec_and_parse",
                    target_node="r1",
                    command="ping",
                    parser="text",
                    success_condition={},
                )
            )
        ]),
        topology=TopologySpecification(nodes=[
            Node(name="r1", type=NodeType.ROUTER, platform=Platform.FRR)
        ])
    )

def test_controller_saves_reasoning_trace(mock_task):
    """Test that controller extracts and saves reasoning_trace."""
    
    # Mock infrastructure and evaluators
    controller = InteractiveBenchmarkController(
        infrastructure=MagicMock(),
        property_evaluator=MagicMock(),
        scoring_calculator=MagicMock(),
        validity_checker=MagicMock()
    )
    
    # Mock property evaluation result
    controller.property_evaluator.evaluate_all_properties.return_value = [
        PropertyEvaluationResult(
            property_id="p1", 
            satisfied=True, 
            observation_raw="", 
            evaluation_time_seconds=1.0
        )
    ]
    
    # Mock scoring and validity to return valid objects
    controller.scoring_calculator.compute_all_scores.return_value = ScoringResult(
        completeness=1.0, robustness=1.0, syntactic_validity=1.0, efficiency=1.0, final_score=1.0
    )
    controller.validity_checker.check_validity.return_value = ValidityCheck(
        is_valid_solution=True, condition_a_syntactic=True, condition_b_semantic=True
    )
    
    # Mock session
    mock_session = MagicMock()
    mock_session.start.return_value = MagicMock(nodes=[], session_id="test_session")
    mock_session.is_active = False # Finish immediately
    mock_session.get_approach.return_value = [("r1", "ping 1.1.1.1")]
    mock_session.get_execution_log.return_value = [("r1", "ping 1.1.1.1", True)]
    mock_session.get_session_status.return_value = MagicMock(turns_used=5)
    
    dagent_url = "http://dagent:8000"
    
    # Mock dagent response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True, 
        "reasoning_trace": [{"step": "test", "content": "debug"}],
        "actions": []
    }
    
    with patch("benchmark.interactive_controller.InteractiveSession", return_value=mock_session):
        with patch("benchmark.interactive_controller.BenchmarkMCPServer"):
            with patch("threading.Thread"):
                with patch("httpx.Client") as mock_client:
                    mock_client.return_value.__enter__.return_value.post.return_value = mock_response
                    
                    result = controller.run_interactive(
                        task=mock_task,
                        testee_id="test_agent",
                        dagent_endpoint=dagent_url,
                        turn_limit=10,
                        time_limit=10,
                        wait_for_submit=False # Don't wait loop
                    )
                    
                    assert result.success
                    assert len(result.reasoning_trace) == 1
                    assert result.reasoning_trace[0]["content"] == "debug"
