"""
Unit tests for task generators.

Tests that task generators produce valid tasks with correct structure.
"""
import sys
from pathlib import Path
import pytest

# Add generators to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "benchmark-tasks" / "generators"))

from generate_reachability_tasks import generate_reachability_tasks
from generate_bgp_tasks import generate_bgp_tasks
from generate_ospf_tasks import generate_ospf_tasks
from generate_vlan_tasks import generate_vlan_tasks
from generate_acl_tasks import generate_acl_tasks
from generate_firewall_tasks import generate_firewall_tasks
from generate_route_redistribution_tasks import generate_route_redistribution_tasks
from generate_mixed_platform_tasks import generate_mixed_platform_tasks


class TestReachabilityGenerator:
    """Test reachability task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_reachability_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 100, f"Expected 100+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_reachability_tasks()
        for task in tasks[:5]:  # Check first 5
            assert "task_id" in task
            assert "description" in task
            assert "platform" in task
            assert "topology" in task
            assert "intent" in task
            assert "convergence" in task

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_reachability_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))


class TestBGPGenerator:
    """Test BGP task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_bgp_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 80, f"Expected 80+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_bgp_tasks()
        for task in tasks[:5]:
            assert "task_id" in task
            assert "bgp" in task["task_id"].lower()
            assert "topology" in task
            assert "nodes" in task["topology"]

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_bgp_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))


class TestOSPFGenerator:
    """Test OSPF task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_ospf_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 80, f"Expected 80+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_ospf_tasks()
        for task in tasks[:5]:
            assert "task_id" in task
            assert "ospf" in task["task_id"].lower()
            assert "topology" in task

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_ospf_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))


class TestVLANGenerator:
    """Test VLAN task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_vlan_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 40, f"Expected 40+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_vlan_tasks()
        for task in tasks[:5]:
            assert "task_id" in task
            assert "vlan" in task["task_id"].lower()
            assert "topology" in task
            assert "intent" in task
            assert "properties" in task["intent"]

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_vlan_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))

    def test_vlan_properties_present(self):
        """Test that VLAN tasks have VLAN-related properties"""
        tasks = generate_vlan_tasks()
        for task in tasks[:5]:
            props = task["intent"]["properties"]
            assert len(props) > 0
            # At least one property should be VLAN-related
            vlan_related = any("vlan" in p.get("type", "").lower() or 
                              "vlan" in p.get("id", "").lower() 
                              for p in props)
            assert vlan_related, f"Task {task['task_id']} has no VLAN-related properties"


class TestAllGenerators:
    """Cross-generator tests"""

    def test_total_task_count(self):
        """Test that total task count meets target"""
        reach = len(generate_reachability_tasks())
        bgp = len(generate_bgp_tasks())
        ospf = len(generate_ospf_tasks())
        vlan = len(generate_vlan_tasks())
        acl = len(generate_acl_tasks())
        fw = len(generate_firewall_tasks())
        redist = len(generate_route_redistribution_tasks())
        mixed = len(generate_mixed_platform_tasks())
        
        total = reach + bgp + ospf + vlan + acl + fw + redist + mixed
        print(f"Task counts: Reach={reach}, BGP={bgp}, OSPF={ospf}, VLAN={vlan}, ACL={acl}, FW={fw}, Redist={redist}, Mixed={mixed}, Total={total}")
        
        # After all generators, we want 800+ tasks
        assert total >= 800, f"Expected 800+ total tasks, got {total}"

    def test_no_cross_generator_id_conflicts(self):
        """Test that no task IDs conflict across generators"""
        all_ids = []
        all_ids.extend([t["task_id"] for t in generate_reachability_tasks()])
        all_ids.extend([t["task_id"] for t in generate_bgp_tasks()])
        all_ids.extend([t["task_id"] for t in generate_ospf_tasks()])
        all_ids.extend([t["task_id"] for t in generate_vlan_tasks()])
        all_ids.extend([t["task_id"] for t in generate_acl_tasks()])
        all_ids.extend([t["task_id"] for t in generate_firewall_tasks()])
        all_ids.extend([t["task_id"] for t in generate_route_redistribution_tasks()])
        all_ids.extend([t["task_id"] for t in generate_mixed_platform_tasks()])
        
        assert len(all_ids) == len(set(all_ids)), "Found duplicate task IDs across generators"

    def test_all_tasks_validate_with_pydantic(self):
        """Test that all generated tasks can be validated with TaskDefinition model"""
        from benchmark.models.task import TaskDefinition
        
        all_tasks = []
        all_tasks.extend(generate_reachability_tasks())
        all_tasks.extend(generate_bgp_tasks())
        all_tasks.extend(generate_ospf_tasks())
        all_tasks.extend(generate_vlan_tasks())
        all_tasks.extend(generate_acl_tasks())
        all_tasks.extend(generate_firewall_tasks())
        all_tasks.extend(generate_route_redistribution_tasks())
        all_tasks.extend(generate_mixed_platform_tasks())
        
        errors = []
        for task in all_tasks:
            try:
                TaskDefinition.model_validate(task)
            except Exception as e:
                errors.append(f"{task['task_id']}: {e}")
        
        if errors:
            # Show first 5 errors
            error_msg = "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more errors"
            pytest.fail(f"Task validation failed:\n{error_msg}")


class TestACLGenerator:
    """Test ACL task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_acl_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 100, f"Expected 100+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_acl_tasks()
        for task in tasks[:5]:
            assert "task_id" in task
            assert "acl" in task["task_id"].lower()
            assert "topology" in task
            assert "intent" in task
            assert "properties" in task["intent"]

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_acl_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))


class TestFirewallGenerator:
    """Test Firewall task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_firewall_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 100, f"Expected 100+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_firewall_tasks()
        for task in tasks[:5]:
            assert "task_id" in task
            assert "fw" in task["task_id"].lower()
            assert "topology" in task
            assert "intent" in task

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_firewall_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))


class TestRouteRedistributionGenerator:
    """Test Route Redistribution task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_route_redistribution_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 100, f"Expected 100+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_route_redistribution_tasks()
        for task in tasks[:5]:
            assert "task_id" in task
            assert "redist" in task["task_id"].lower()
            assert "topology" in task
            assert "intent" in task

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_route_redistribution_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))


class TestMixedPlatformGenerator:
    """Test Mixed Platform task generator"""

    def test_generates_tasks(self):
        """Test that generator produces tasks"""
        tasks = generate_mixed_platform_tasks()
        assert len(tasks) > 0
        assert len(tasks) >= 90, f"Expected 90+ tasks, got {len(tasks)}"

    def test_task_structure(self):
        """Test that tasks have required fields"""
        tasks = generate_mixed_platform_tasks()
        for task in tasks[:5]:
            assert "task_id" in task
            assert "mixed" in task["task_id"].lower()
            assert "topology" in task
            assert "intent" in task
            
            # Check mixed_platforms field
            assert "mixed_platforms" in task
            assert isinstance(task["mixed_platforms"], list)
            assert len(task["mixed_platforms"]) > 1
            
            # Check node platforms
            platforms = [n["platform"] for n in task["topology"]["nodes"]]
            assert len(set(platforms)) > 1, "Task should have nodes with different platforms"

    def test_unique_task_ids(self):
        """Test that all task IDs are unique"""
        tasks = generate_mixed_platform_tasks()
        task_ids = [t["task_id"] for t in tasks]
        assert len(task_ids) == len(set(task_ids))
