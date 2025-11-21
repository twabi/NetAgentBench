#!/usr/bin/env python3
"""
Generate JSON schema from Pydantic models for task and submission validation.

This script generates a comprehensive JSON schema that can be used by external
tools to validate task definition files and submission files.
"""
import json
from pathlib import Path
from typing import Dict, Any

from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission


def generate_combined_schema() -> Dict[str, Any]:
    """Generate combined JSON schema for TaskDefinition and Submission models"""
    
    # Generate schemas for both models
    task_schema = TaskDefinition.model_json_schema()
    submission_schema = Submission.model_json_schema()
    
    # Create combined schema with definitions
    combined_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://network-config-benchmark.org/schemas/combined.json",
        "title": "Network Configuration Benchmark Schema",
        "description": "Combined schema for task definitions and submissions",
        "definitions": {
            "TaskDefinition": task_schema,
            "Submission": submission_schema
        },
        "oneOf": [
            {
                "$ref": "#/definitions/TaskDefinition"
            },
            {
                "$ref": "#/definitions/Submission"
            }
        ],
        "examples": [
            {
                "description": "Example task definition",
                "$ref": "#/definitions/TaskDefinition"
            },
            {
                "description": "Example submission",
                "$ref": "#/definitions/Submission"
            }
        ]
    }
    
    return combined_schema


def main():
    """Generate and save the JSON schema"""
    
    # Generate schema
    schema = generate_combined_schema()
    
    # Determine output path
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    schema_path = project_root / "tasks" / "schema.json"
    
    # Ensure tasks directory exists
    schema_path.parent.mkdir(exist_ok=True)
    
    # Write schema to file
    with open(schema_path, 'w') as f:
        json.dump(schema, f, indent=2)
    
    print(f"✅ Generated JSON schema: {schema_path}")
    print(f"📊 Schema includes {len(schema['definitions'])} model definitions")
    print(f"🔗 Schema ID: {schema['$id']}")


if __name__ == "__main__":
    main()
