"""
Unit tests for task file validation.

Tests that task definition files can be loaded, validated, and meet requirements.
Uses TDD approach - tests written before task files exist.
"""
import json
import pytest
from pathlib import Path
from typing import Dict, Any

from benchmark.models.task import TaskDefinition, Platform, PropertyType
from benchmark.models.submission import Submission


class TestTaskFileValidation:
    """Test that task files can be loaded and validated correctly"""

    @pytest.fixture
    def tasks_dir(self) -> Path:
        """Path to tasks directory"""
        return Path(__file__).parent.parent.parent / "tasks"

    def test_basic_reachability_task_loads(self, tasks_dir: Path):
        """Test that basic_reachability.json loads without validation errors"""
        task_file = tasks_dir / "basic_reachability.json"
        
        # RED: This test will fail until we create the file
        assert task_file.exists(), f"Task file {task_file} should exist"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        # Validate with Pydantic
        task = TaskDefinition.model_validate(task_data)
        
        # Verify basic structure
        assert task.task_id == "basic_reachability"
        assert task.platform == Platform.FRR
        assert len(task.topology.nodes) == 2
        assert len(task.topology.links) == 1
        assert len(task.intent.properties) == 1

    def test_basic_reachability_has_correct_nodes(self, tasks_dir: Path):
        """Test that basic_reachability has exactly 2 nodes (R1, R2)"""
        task_file = tasks_dir / "basic_reachability.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        node_names = {node.name for node in task.topology.nodes}
        assert node_names == {"R1", "R2"}
        
        # Verify node types
        for node in task.topology.nodes:
            assert node.type == "router"

    def test_basic_reachability_has_reachability_property(self, tasks_dir: Path):
        """Test that basic_reachability has 1 reachability property with text parser"""
        task_file = tasks_dir / "basic_reachability.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert len(task.intent.properties) == 1
        prop = task.intent.properties[0]
        
        assert prop.type == PropertyType.REACHABILITY
        assert prop.evaluation.parser == "text"
        assert "ping" in prop.evaluation.command.lower()
        assert "3 packets transmitted, 3 packets received" in prop.evaluation.success_condition.get("contains_text", "")

    def test_basic_reachability_convergence_config(self, tasks_dir: Path):
        """Test that convergence config is sensible (30s timeout)"""
        task_file = tasks_dir / "basic_reachability.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.convergence.timeout_seconds == 30
        assert task.convergence.check_interval_seconds == 2

    def test_bgp_basic_task_loads(self, tasks_dir: Path):
        """Test that bgp_basic.json loads correctly"""
        task_file = tasks_dir / "bgp_basic.json"
        
        assert task_file.exists(), f"Task file {task_file} should exist"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.task_id == "bgp_basic"
        assert task.platform == Platform.FRR
        assert len(task.topology.nodes) == 2
        assert len(task.intent.properties) == 3

    def test_bgp_basic_has_three_properties(self, tasks_dir: Path):
        """Test that bgp_basic has 3 properties with different parser types"""
        task_file = tasks_dir / "bgp_basic.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert len(task.intent.properties) == 3
        
        # Check property types
        property_types = {prop.type for prop in task.intent.properties}
        expected_types = {PropertyType.BGP_CONFIGURATION, PropertyType.ROUTE_EXISTS, PropertyType.REACHABILITY}
        assert property_types == expected_types
        
        # Check parser types
        parser_types = {prop.evaluation.parser for prop in task.intent.properties}
        assert "json" in parser_types
        assert "regex" in parser_types
        assert "text" in parser_types

    def test_bgp_basic_has_optimal_solution(self, tasks_dir: Path):
        """Test that bgp_basic specifies optimal solution command count"""
        task_file = tasks_dir / "bgp_basic.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.optimal_solution is not None
        assert task.optimal_solution.command_count == 12
        assert "BGP" in task.optimal_solution.description

    def test_bgp_basic_evaluation_nodes_exist(self, tasks_dir: Path):
        """Test that all evaluation procedures reference valid nodes"""
        task_file = tasks_dir / "bgp_basic.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        node_names = {node.name for node in task.topology.nodes}
        
        for prop in task.intent.properties:
            assert prop.evaluation.target_node in node_names

    def test_bgp_basic_property_ids_unique(self, tasks_dir: Path):
        """Test that all properties have unique IDs"""
        task_file = tasks_dir / "bgp_basic.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        property_ids = [prop.id for prop in task.intent.properties]
        assert len(property_ids) == len(set(property_ids))

    def test_ospf_3node_task_loads(self, tasks_dir: Path):
        """Test that ospf_3node.json loads correctly"""
        task_file = tasks_dir / "ospf_3node.json"
        
        assert task_file.exists(), f"Task file {task_file} should exist"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.task_id == "ospf_3node"
        assert task.platform == Platform.FRR
        assert len(task.topology.nodes) == 3
        assert len(task.topology.links) == 2

    def test_ospf_3node_has_three_nodes_two_links(self, tasks_dir: Path):
        """Test that ospf_3node has 3 nodes and 2 links"""
        task_file = tasks_dir / "ospf_3node.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert len(task.topology.nodes) == 3
        assert len(task.topology.links) == 2
        
        node_names = {node.name for node in task.topology.nodes}
        assert node_names == {"R1", "R2", "R3"}

    def test_ospf_3node_link_endpoints_exist(self, tasks_dir: Path):
        """Test that link endpoints reference existing nodes"""
        task_file = tasks_dir / "ospf_3node.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        # This should pass Pydantic validation if links reference existing nodes
        node_names = {node.name for node in task.topology.nodes}
        
        for link in task.topology.links:
            for endpoint in link.endpoints:
                node_name = endpoint.split(":")[0]
                assert node_name in node_names

    def test_ospf_3node_has_four_properties(self, tasks_dir: Path):
        """Test that ospf_3node has 4 properties"""
        task_file = tasks_dir / "ospf_3node.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert len(task.intent.properties) == 4

    def test_ospf_3node_convergence_timeout_adequate(self, tasks_dir: Path):
        """Test that convergence timeout is adequate for OSPF (60s recommended)"""
        task_file = tasks_dir / "ospf_3node.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.convergence.timeout_seconds >= 60


class TestSolutionFileValidation:
    """Test that solution files can be loaded and validated correctly"""

    @pytest.fixture
    def solutions_dir(self) -> Path:
        """Path to solutions directory"""
        return Path(__file__).parent.parent.parent / "tasks" / "solutions"

    def test_basic_reachability_solutions_load(self, solutions_dir: Path):
        """Test that all basic_reachability solution files load"""
        solution_files = [
            "basic_reachability_valid.json",
            "basic_reachability_invalid.json", 
            "basic_reachability_partial.json"
        ]
        
        for solution_file in solution_files:
            file_path = solutions_dir / solution_file
            assert file_path.exists(), f"Solution file {file_path} should exist"
            
            with open(file_path, 'r') as f:
                solution_data = json.load(f)
            
            submission = Submission.model_validate(solution_data)
            assert submission.task_id == "basic_reachability"

    def test_bgp_basic_solutions_load(self, solutions_dir: Path):
        """Test that all bgp_basic solution files load"""
        solution_files = [
            "bgp_basic_valid.json",
            "bgp_basic_invalid.json",
            "bgp_basic_partial.json"
        ]
        
        for solution_file in solution_files:
            file_path = solutions_dir / solution_file
            assert file_path.exists(), f"Solution file {file_path} should exist"
            
            with open(file_path, 'r') as f:
                solution_data = json.load(f)
            
            submission = Submission.model_validate(solution_data)
            assert submission.task_id == "bgp_basic"

    def test_ospf_3node_solutions_load(self, solutions_dir: Path):
        """Test that all ospf_3node solution files load"""
        solution_files = [
            "ospf_3node_valid.json",
            "ospf_3node_invalid.json",
            "ospf_3node_partial.json"
        ]
        
        for solution_file in solution_files:
            file_path = solutions_dir / solution_file
            assert file_path.exists(), f"Solution file {file_path} should exist"
            
            with open(file_path, 'r') as f:
                solution_data = json.load(f)
            
            submission = Submission.model_validate(solution_data)
            assert submission.task_id == "ospf_3node"

    def test_solution_files_have_commands(self, solutions_dir: Path):
        """Test that all solution files have non-empty command sequences"""
        solution_files = [
            "basic_reachability_valid.json",
            "bgp_basic_valid.json",
            "ospf_3node_valid.json"
        ]
        
        for solution_file in solution_files:
            file_path = solutions_dir / solution_file
            
            with open(file_path, 'r') as f:
                solution_data = json.load(f)
            
            submission = Submission.model_validate(solution_data)
            
            assert len(submission.approach.commands) > 0
            for cmd_seq in submission.approach.commands:
                assert len(cmd_seq.commands) > 0
