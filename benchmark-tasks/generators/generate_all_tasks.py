#!/usr/bin/env python3
"""
Generate all benchmark tasks programmatically.

Usage:
    python generate_all_tasks.py --property-type all
    python generate_all_tasks.py --property-type reachability
    python generate_all_tasks.py --property-type bgp_configuration
    python generate_all_tasks.py --property-type ospf_configuration
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add current directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from generate_reachability_tasks import generate_reachability_tasks
from generate_bgp_tasks import generate_bgp_tasks
from generate_ospf_tasks import generate_ospf_tasks


def save_tasks(tasks: List[Dict[str, Any]], output_dir: Path) -> None:
    """
    Save tasks to individual JSON files.

    Args:
        tasks: List of task dictionaries
        output_dir: Directory to save tasks
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for task in tasks:
        task_id = task["task_id"]
        task_file = output_dir / f"{task_id}.json"
        
        with open(task_file, 'w') as f:
            json.dump(task, f, indent=2)


def generate_task_index(base_dir: Path, task_counts: Dict[str, int]) -> Dict[str, Any]:
    """
    Generate task index with metadata.

    Args:
        base_dir: Base directory for benchmark tasks
        task_counts: Count of tasks by property type

    Returns:
        Index dictionary
    """
    total_tasks = sum(task_counts.values())

    index = {
        "version": "1.0",
        "generated": datetime.utcnow().isoformat() + "Z",
        "total_tasks": total_tasks,
        "property_types": {
            "reachability": {
                "count": task_counts.get("reachability", 0),
                "description": "Network connectivity and reachability between nodes",
                "tasks_dir": "property_types/reachability/tasks/"
            },
            "bgp_configuration": {
                "count": task_counts.get("bgp_configuration", 0),
                "description": "BGP protocol configuration, session establishment, and route exchange",
                "tasks_dir": "property_types/bgp_configuration/tasks/"
            },
            "ospf_configuration": {
                "count": task_counts.get("ospf_configuration", 0),
                "description": "OSPF protocol configuration, adjacencies, and routing",
                "tasks_dir": "property_types/ospf_configuration/tasks/"
            }
        },
        "topology_patterns": {
            "linear": "Chain topology",
            "star": "Hub-spoke topology",
            "ring": "Circular topology",
            "mesh": "Full mesh topology",
            "tree": "Hierarchical tree topology"
        }
    }

    return index


def main() -> None:
    """Main entry point for task generation."""
    parser = argparse.ArgumentParser(description="Generate benchmark tasks")
    parser.add_argument(
        "--property-type",
        choices=["all", "reachability", "bgp_configuration", "ospf_configuration"],
        default="all",
        help="Which property type tasks to generate"
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent),
        help="Output directory for generated tasks (default: benchmark-tasks/)"
    )

    args = parser.parse_args()
    base_dir = Path(args.output_dir)

    generators = {
        "reachability": generate_reachability_tasks,
        "bgp_configuration": generate_bgp_tasks,
        "ospf_configuration": generate_ospf_tasks,
    }

    if args.property_type == "all":
        property_types = list(generators.keys())
    else:
        property_types = [args.property_type]

    task_counts = {}
    total_generated = 0

    for prop_type in property_types:
        print(f"Generating {prop_type} tasks...")
        tasks = generators[prop_type]()

        # Save tasks to files
        output_path = base_dir / "property_types" / prop_type / "tasks"
        save_tasks(tasks, output_path)

        print(f"  Generated {len(tasks)} {prop_type} tasks")
        task_counts[prop_type] = len(tasks)
        total_generated += len(tasks)

    print(f"\nTotal tasks generated: {total_generated}")

    # Generate and save index
    index = generate_task_index(base_dir, task_counts)
    index_file = base_dir / "index.json"
    
    with open(index_file, 'w') as f:
        json.dump(index, f, indent=2)
    
    print(f"Task index generated: {index_file}")
    print("\n✅ Task generation complete!")
    print(f"\nBreakdown:")
    for prop_type, count in task_counts.items():
        print(f"  - {prop_type}: {count} tasks")


if __name__ == "__main__":
    main()

