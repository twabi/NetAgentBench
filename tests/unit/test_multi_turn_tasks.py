"""
Unit tests for multi-turn reference task files.

Tests that multi-turn task definitions are valid, follow research design,
and can be loaded by the benchmark system.
"""
import json
import pytest
from pathlib import Path

from benchmark.models.task import TaskDefinition, PropertyType


class TestMultiTurnTaskValidation:
    """Tests for multi-turn reference task files"""

    @pytest.fixture
    def multi_turn_dir(self) -> Path:
        """Path to multi-turn tasks directory"""
        return Path(__file__).parent.parent.parent / "tasks" / "archive" / "multi_turn"

    def test_small_campus_baseline_loads(self, multi_turn_dir: Path):
        """Test that small_campus_baseline.json loads without validation errors"""
        task_file = multi_turn_dir / "small_campus_baseline.json"
        
        assert task_file.exists(), f"Task file {task_file} should exist"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.task_id == "small_campus_baseline"
        assert len(task.topology.nodes) == 15
        assert task.convergence.timeout_seconds >= 60

    def test_small_campus_has_ring_topology(self, multi_turn_dir: Path):
        """Test that small campus has 15 links forming a ring"""
        task_file = multi_turn_dir / "small_campus_baseline.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        # Ring should have exactly same number of links as nodes
        assert len(task.topology.links) == 15

    def test_small_campus_has_ospf_and_reachability(self, multi_turn_dir: Path):
        """Test that small campus has both OSPF and reachability properties"""
        task_file = multi_turn_dir / "small_campus_baseline.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        prop_types = {prop.type for prop in task.intent.properties}
        assert PropertyType.OSPF_CONFIGURATION in prop_types
        assert PropertyType.REACHABILITY in prop_types

    def test_small_campus_has_research_context(self, multi_turn_dir: Path):
        """Test that task includes research context metadata"""
        task_file = multi_turn_dir / "small_campus_baseline.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        assert "research_context" in task_data
        assert "research_question" in task_data["research_context"]
        assert "RQ1" in task_data["research_context"]["research_question"]

    def test_medium_mixed_platform_loads(self, multi_turn_dir: Path):
        """Test that medium_mixed_platform.json loads correctly"""
        task_file = multi_turn_dir / "medium_mixed_platform.json"
        
        assert task_file.exists(), f"Task file {task_file} should exist"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.task_id == "medium_mixed_platform"
        assert len(task.topology.nodes) == 35

    def test_medium_has_spine_leaf_topology(self, multi_turn_dir: Path):
        """Test that medium task has spine-leaf structure with roles"""
        task_file = multi_turn_dir / "medium_mixed_platform.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        # Count nodes by name prefix
        spines = [n for n in task.topology.nodes if n.name.startswith("SPINE")]
        leaves = [n for n in task.topology.nodes if n.name.startswith("LEAF")]
        
        assert len(spines) == 5, "Should have 5 spine nodes"
        assert len(leaves) == 30, "Should have 30 leaf nodes"

    def test_medium_has_bgp_properties(self, multi_turn_dir: Path):
        """Test that medium task includes BGP configuration properties"""
        task_file = multi_turn_dir / "medium_mixed_platform.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        prop_types = {prop.type for prop in task.intent.properties}
        assert PropertyType.BGP_CONFIGURATION in prop_types

    def test_medium_tests_role_specialization(self, multi_turn_dir: Path):
        """Test that medium task is designed for RQ2 (role specialization)"""
        task_file = multi_turn_dir / "medium_mixed_platform.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        assert "research_context" in task_data
        assert "RQ2" in task_data["research_context"]["research_question"]

    def test_large_sp_core_loads(self, multi_turn_dir: Path):
        """Test that large_sp_core.json loads correctly"""
        task_file = multi_turn_dir / "large_sp_core.json"
        
        assert task_file.exists(), f"Task file {task_file} should exist"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        assert task.task_id == "large_sp_core"
        assert len(task.topology.nodes) == 50

    def test_large_has_three_tier_structure(self, multi_turn_dir: Path):
        """Test that large task has core, spine, and PE tiers"""
        task_file = multi_turn_dir / "large_sp_core.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        cores = [n for n in task.topology.nodes if n.name.startswith("CORE")]
        spines = [n for n in task.topology.nodes if n.name.startswith("SPE")]
        pes = [n for n in task.topology.nodes if n.name.startswith("PE")]
        
        assert len(cores) == 2, "Should have 2 core nodes"
        assert len(spines) == 8, "Should have 8 spine nodes"
        assert len(pes) == 40, "Should have 40 PE nodes"

    def test_large_has_route_reflector_properties(self, multi_turn_dir: Path):
        """Test that large task includes route reflector configuration"""
        task_file = multi_turn_dir / "large_sp_core.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        task = TaskDefinition.model_validate(task_data)
        
        # Check for route reflector property
        prop_ids = {prop.id for prop in task.intent.properties}
        assert any("route_reflector" in pid for pid in prop_ids)

    def test_large_tests_parallelism(self, multi_turn_dir: Path):
        """Test that large task is designed for RQ3 (parallelism)"""
        task_file = multi_turn_dir / "large_sp_core.json"
        
        with open(task_file, 'r') as f:
            task_data = json.load(f)
        
        assert "research_context" in task_data
        assert "RQ3" in task_data["research_context"]["research_question"]
        assert "parallel_decomposition" in task_data["research_context"]

    def test_all_tasks_have_unique_ids(self, multi_turn_dir: Path):
        """Test that all multi-turn tasks have unique IDs"""
        task_files = list(multi_turn_dir.glob("*.json"))
        
        task_ids = []
        for task_file in task_files:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            task = TaskDefinition.model_validate(task_data)
            task_ids.append(task.task_id)
        
        assert len(task_ids) == len(set(task_ids)), "Task IDs must be unique"

    def test_all_tasks_have_evaluation_mode(self, multi_turn_dir: Path):
        """Test that all multi-turn tasks specify evaluation_mode"""
        task_files = list(multi_turn_dir.glob("*.json"))
        
        for task_file in task_files:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            
            assert "evaluation_mode" in task_data, f"{task_file.name} missing evaluation_mode"
            assert task_data["evaluation_mode"] == "multi_turn"

    def test_all_tasks_have_valid_property_nodes(self, multi_turn_dir: Path):
        """Test that all evaluation target_nodes exist in topology"""
        task_files = list(multi_turn_dir.glob("*.json"))
        
        for task_file in task_files:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            
            task = TaskDefinition.model_validate(task_data)
            node_names = {node.name for node in task.topology.nodes}
            
            for prop in task.intent.properties:
                assert prop.evaluation.target_node in node_names, \
                    f"{task_file.name}: property {prop.id} references unknown node {prop.evaluation.target_node}"

    def test_small_medium_large_complexity_ordering(self, multi_turn_dir: Path):
        """Test that tasks follow small < medium < large complexity ordering"""
        small = multi_turn_dir / "small_campus_baseline.json"
        medium = multi_turn_dir / "medium_mixed_platform.json"
        large = multi_turn_dir / "large_sp_core.json"
        
        with open(small) as f:
            small_task = TaskDefinition.model_validate(json.load(f))
        with open(medium) as f:
            medium_task = TaskDefinition.model_validate(json.load(f))
        with open(large) as f:
            large_task = TaskDefinition.model_validate(json.load(f))
        
        # Node count ordering
        assert len(small_task.topology.nodes) < len(medium_task.topology.nodes)
        assert len(medium_task.topology.nodes) < len(large_task.topology.nodes)
        
        # Property count should increase with complexity
        assert len(small_task.intent.properties) <= len(medium_task.intent.properties)
        assert len(medium_task.intent.properties) <= len(large_task.intent.properties)
