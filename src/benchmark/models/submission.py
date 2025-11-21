"""
Pydantic models for testee submissions.

This module defines all models related to configuration submissions from
testees (LLMs, humans, or baseline systems).

Based on the FSM formalization document.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Submission Models (Definition 14 in formalization)
# ============================================================================


class CommandSequence(BaseModel):
    """
    Command sequence for a specific node.
    
    Groups commands that should be executed on a single node.
    This provides structure to the configuration approach.
    """

    node: str = Field(..., description="Target node name")
    commands: List[str] = Field(
        ..., min_length=1, description="List of commands to execute on this node"
    )


class Approach(BaseModel):
    """
    Configuration approach A = ⟨a₁, a₂, ..., aₙ⟩ ∈ Σ_config^+ (Definition 14).
    
    Represents the complete configuration strategy provided by the testee
    to achieve the specified intent starting from the initial state.
    
    The approach is organized as command sequences per node for clarity,
    but logically represents a sequential execution plan.
    """

    description: Optional[str] = Field(
        None, description="Human-readable description of the configuration approach"
    )
    commands: List[CommandSequence] = Field(
        ...,
        min_length=1,
        description="Command sequences organized by target node",
    )


class Submission(BaseModel):
    """
    Complete submission from a testee (LLM, human, or baseline system).
    
    This is the standardized input format for the benchmark - it links
    a testee's configuration approach to a specific task.
    
    Attributes:
        task_id: References the TaskDefinition being solved
        testee_id: Unique identifier for the testee (e.g., "gpt4_20251013", "human_expert_1")
        testee_type: Type of testee ("llm", "human", "baseline")
        approach: The configuration approach proposed by the testee
    """

    task_id: str = Field(..., description="Task identifier being solved")
    testee_id: str = Field(..., description="Unique testee identifier")
    testee_type: str = Field(
        ..., description="Type of testee: 'llm', 'human', or 'baseline'"
    )
    approach: Approach = Field(..., description="Proposed configuration approach")

