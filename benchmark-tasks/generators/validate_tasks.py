#!/usr/bin/env python3
"""
Validate all generated tasks.

Usage:
    python validate_tasks.py --property-type all
    python validate_tasks.py --property-type reachability
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.models.task import TaskDefinition


def load_tasks_from_dir(tasks_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all tasks from a directory.

    Args:
        tasks_dir: Directory containing task JSON files

    Returns:
        List of task dictionaries
    """
    if not tasks_dir.exists():
        print(f"  ⚠️  Directory not found: {tasks_dir}")
        return []

    tasks = []
    task_files = sorted(tasks_dir.glob("*.json"))

    for task_file in task_files:
        try:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
                tasks.append(task_data)
        except Exception as e:
            print(f"  ❌ Failed to load {task_file.name}: {e}")

    return tasks


def validate_task_schema(task_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate task against Pydantic schema.

    Args:
        task_data: Task dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        TaskDefinition.model_validate(task_data)
        return True, ""
    except Exception as e:
        return False, str(e)


def validate_topology(task_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate topology structure.

    Args:
        task_data: Task dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        topology = task_data.get("topology", {})
        nodes = topology.get("nodes", [])
        links = topology.get("links", [])

        if not nodes:
            return False, "No nodes in topology"

        # Check that all link endpoints reference existing nodes
        node_names = {node["name"] for node in nodes}
        for link in links:
            for endpoint in link["endpoints"]:
                node_name = endpoint.split(":")[0]
                if node_name not in node_names:
                    return False, f"Link references non-existent node: {node_name}"

        return True, ""
    except Exception as e:
        return False, f"Topology validation error: {str(e)}"


def validate_properties(task_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate intent properties.

    Args:
        task_data: Task dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        intent = task_data.get("intent", {})
        properties = intent.get("properties", [])

        if not properties:
            return False, "No properties defined"

        for prop in properties:
            # Check required fields
            if "id" not in prop:
                return False, "Property missing 'id' field"
            if "type" not in prop:
                return False, "Property missing 'type' field"
            if "evaluation" not in prop:
                return False, "Property missing 'evaluation' field"

            eval_config = prop["evaluation"]
            if "target_node" not in eval_config:
                return False, f"Property {prop['id']} missing target_node"
            if "command" not in eval_config:
                return False, f"Property {prop['id']} missing command"

        return True, ""
    except Exception as e:
        return False, f"Properties validation error: {str(e)}"


def validate_property_type(
    property_type: str,
    base_dir: Path
) -> tuple[int, int, List[str]]:
    """
    Validate all tasks for a property type.

    Args:
        property_type: Property type name
        base_dir: Base directory for tasks

    Returns:
        Tuple of (valid_count, invalid_count, errors)
    """
    tasks_dir = base_dir / "property_types" / property_type / "tasks"
    print(f"\nValidating {property_type} tasks...")

    tasks = load_tasks_from_dir(tasks_dir)
    if not tasks:
        return 0, 0, ["No tasks found"]

    valid_count = 0
    invalid_count = 0
    errors = []

    for task_data in tasks:
        task_id = task_data.get("task_id", "unknown")

        # Schema validation
        is_valid, error = validate_task_schema(task_data)
        if not is_valid:
            errors.append(f"  ❌ {task_id}: Schema validation failed - {error}")
            invalid_count += 1
            continue

        # Topology validation
        is_valid, error = validate_topology(task_data)
        if not is_valid:
            errors.append(f"  ❌ {task_id}: Topology validation failed - {error}")
            invalid_count += 1
            continue

        # Properties validation
        is_valid, error = validate_properties(task_data)
        if not is_valid:
            errors.append(f"  ❌ {task_id}: Properties validation failed - {error}")
            invalid_count += 1
            continue

        valid_count += 1

    return valid_count, invalid_count, errors


def main() -> None:
    """Main entry point for task validation."""
    parser = argparse.ArgumentParser(description="Validate benchmark tasks")
    parser.add_argument(
        "--property-type",
        choices=["all", "reachability", "bgp_configuration", "ospf_configuration"],
        default="all",
        help="Which property type tasks to validate"
    )
    parser.add_argument(
        "--base-dir",
        default=str(Path(__file__).parent.parent),
        help="Base directory for benchmark tasks (default: benchmark-tasks/)"
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir)

    property_types = {
        "reachability": "reachability",
        "bgp_configuration": "bgp_configuration",
        "ospf_configuration": "ospf_configuration",
    }

    if args.property_type == "all":
        types_to_validate = list(property_types.keys())
    else:
        types_to_validate = [args.property_type]

    total_valid = 0
    total_invalid = 0
    all_errors = []

    for prop_type in types_to_validate:
        valid, invalid, errors = validate_property_type(prop_type, base_dir)
        total_valid += valid
        total_invalid += invalid
        all_errors.extend(errors)

        print(f"  ✓ {valid} valid tasks")
        if invalid > 0:
            print(f"  ✗ {invalid} invalid tasks")

    print(f"\n{'='*60}")
    print(f"Total: {total_valid} valid, {total_invalid} invalid")

    if all_errors:
        print(f"\nErrors found:")
        for error in all_errors[:20]:  # Show first 20 errors
            print(error)
        if len(all_errors) > 20:
            print(f"\n... and {len(all_errors) - 20} more errors")
        sys.exit(1)
    else:
        print("\n✅ All tasks valid!")
        sys.exit(0)


if __name__ == "__main__":
    main()

