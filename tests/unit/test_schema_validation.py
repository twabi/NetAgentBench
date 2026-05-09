"""
Schema validation tests for task and solution files.

Tests that all task and solution files conform to the generated JSON schema.
"""
import json
import pytest
from pathlib import Path
from typing import Dict, Any

from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission


class TestSchemaValidation:
    """Test that all task and solution files conform to the generated schema"""

    @pytest.fixture
    def tasks_dir(self) -> Path:
        """Path to tasks directory"""
        return Path(__file__).parent.parent.parent / "tasks"

    @pytest.fixture
    def solutions_dir(self) -> Path:
        """Path to solutions directory"""
        return Path(__file__).parent.parent.parent / "tasks" / "solutions"

    @pytest.fixture
    def schema_file(self, tasks_dir: Path) -> Path:
        """Path to schema file"""
        return tasks_dir / "schema.json"

    def test_schema_file_exists_and_valid(self, schema_file: Path):
        """Test that schema file exists and is valid JSON"""
        assert schema_file.exists(), f"Schema file {schema_file} should exist"
        
        with open(schema_file, 'r') as f:
            schema_data = json.load(f)
        
        # Basic schema validation
        assert "$schema" in schema_data
        assert "$id" in schema_data
        assert "definitions" in schema_data
        assert "TaskDefinition" in schema_data["definitions"]
        assert "Submission" in schema_data["definitions"]

    def test_all_task_files_validate_against_schema(self, tasks_dir: Path):
        """Test that all task files validate against the schema"""
        task_files = [
            "basic_reachability.json",
            "bgp_basic.json", 
            "ospf_3node.json"
        ]
        
        for task_file in task_files:
            file_path = tasks_dir / task_file
            
            with open(file_path, 'r') as f:
                task_data = json.load(f)
            
            # Validate with Pydantic (which uses the same schema)
            task = TaskDefinition.model_validate(task_data)
            assert task.task_id is not None
            assert task.platform is not None

    def test_all_solution_files_validate_against_schema(self, solutions_dir: Path):
        """Test that all solution files validate against the schema"""
        solution_files = [
            "basic_reachability_valid.json",
            "basic_reachability_invalid.json",
            "basic_reachability_partial.json",
            "bgp_basic_valid.json",
            "bgp_basic_invalid.json",
            "bgp_basic_partial.json",
            "ospf_3node_valid.json",
            "ospf_3node_invalid.json",
            "ospf_3node_partial.json"
        ]
        
        for solution_file in solution_files:
            file_path = solutions_dir / solution_file
            
            with open(file_path, 'r') as f:
                solution_data = json.load(f)
            
            # Validate with Pydantic (which uses the same schema)
            submission = Submission.model_validate(solution_data)
            assert submission.task_id is not None
            assert submission.testee_id is not None
            assert submission.testee_type is not None

    def test_task_solution_pairs_have_matching_task_ids(self, tasks_dir: Path, solutions_dir: Path):
        """Test that task/solution pairs have matching task_ids"""
        task_solution_pairs = [
            ("basic_reachability.json", ["basic_reachability_valid.json", "basic_reachability_invalid.json", "basic_reachability_partial.json"]),
            ("bgp_basic.json", ["bgp_basic_valid.json", "bgp_basic_invalid.json", "bgp_basic_partial.json"]),
            ("ospf_3node.json", ["ospf_3node_valid.json", "ospf_3node_invalid.json", "ospf_3node_partial.json"])
        ]
        
        for task_file, solution_files in task_solution_pairs:
            # Load task
            task_path = tasks_dir / task_file
            with open(task_path, 'r') as f:
                task_data = json.load(f)
            task = TaskDefinition.model_validate(task_data)
            
            # Check each solution file
            for solution_file in solution_files:
                solution_path = solutions_dir / solution_file
                with open(solution_path, 'r') as f:
                    solution_data = json.load(f)
                submission = Submission.model_validate(solution_data)
                
                assert submission.task_id == task.task_id, f"Task ID mismatch: {task_file} vs {solution_file}"

    def test_schema_covers_all_required_fields(self, schema_file: Path):
        """Test that schema covers all required fields for both models"""
        with open(schema_file, 'r') as f:
            schema_data = json.load(f)
        
        task_def = schema_data["definitions"]["TaskDefinition"]
        submission_def = schema_data["definitions"]["Submission"]
        
        # Check TaskDefinition required fields
        task_required = task_def.get("required", [])
        expected_task_fields = ["task_id", "description", "platform", "topology", "intent"]
        for field in expected_task_fields:
            assert field in task_required, f"Required field {field} missing from TaskDefinition schema"
        
        # Check Submission required fields
        submission_required = submission_def.get("required", [])
        expected_submission_fields = ["task_id", "testee_id", "testee_type", "approach"]
        for field in expected_submission_fields:
            assert field in submission_required, f"Required field {field} missing from Submission schema"

    def test_schema_includes_all_enum_values(self, schema_file: Path):
        """Test that schema includes all enum values"""
        with open(schema_file, 'r') as f:
            schema_data = json.load(f)
        
        # Check that Platform enum values are included in TaskDefinition
        task_def = schema_data["definitions"]["TaskDefinition"]
        platform_def = task_def["$defs"]["Platform"]
        assert "enum" in platform_def
        platform_values = platform_def["enum"]
        assert "frr" in platform_values
        assert "cisco_ios" in platform_values
        
        # Check that NodeType enum values are included
        node_type_def = task_def["$defs"]["NodeType"]
        assert "enum" in node_type_def
        node_type_values = node_type_def["enum"]
        assert "router" in node_type_values
        assert "switch" in node_type_values
        
        # Check that PropertyType enum values are included
        property_type_def = task_def["$defs"]["PropertyType"]
        assert "enum" in property_type_def
        property_type_values = property_type_def["enum"]
        assert "reachability" in property_type_values
        assert "bgp_configuration" in property_type_values
        assert "ospf_configuration" in property_type_values
