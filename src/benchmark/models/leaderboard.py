"""
Pydantic models for leaderboard system.

This module defines models for tracking and comparing testee performance
across benchmark runs, supporting both single-turn and multi-turn evaluation modes.
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Leaderboard Entry
# ============================================================================


class LeaderboardEntry(BaseModel):
    """
    Individual entry in a leaderboard.
    
    Represents a single testee's performance on a benchmark run,
    including their score and optional breakdown by metric.
    """

    testee_id: str = Field(..., description="Testee identifier (e.g., 'dagent', 'gpt-4o')")
    model_version: Optional[str] = Field(
        None, description="Model version (e.g., 'gpt-4-0125-preview')"
    )
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Score for this leaderboard's metric"
    )
    run_id: str = Field(..., description="Reference to BenchmarkRunResult")
    timestamp: datetime = Field(..., description="When the run completed")
    num_tasks: int = Field(..., ge=0, description="Number of tasks in the run")
    breakdown: Optional[Dict[str, float]] = Field(
        None, description="Per-metric score breakdown (e.g., {'completeness': 0.9, 'robustness': 0.8})"
    )

    @field_validator("breakdown")
    @classmethod
    def validate_breakdown_scores(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        """Validate that all breakdown scores are within [0, 1]."""
        if v is not None:
            for metric, score in v.items():
                if not 0.0 <= score <= 1.0:
                    raise ValueError(f"Breakdown score for '{metric}' must be between 0 and 1, got {score}")
        return v


# ============================================================================
# Leaderboard
# ============================================================================


class Leaderboard(BaseModel):
    """
    A ranked list of testees for a specific category.
    
    Categories can be:
    - Overall score (single-turn or multi-turn)
    - Specific metric (completeness, robustness, syntactic_validity)
    - Specific property type (reachability, bgp_configuration, etc.)
    
    Entries are maintained in descending order by score.
    """

    leaderboard_id: str = Field(
        ..., description="Unique identifier (e.g., 'overall_single_turn')"
    )
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this leaderboard measures")
    evaluation_mode: str = Field(
        ..., description="Evaluation mode: 'single_turn', 'multi_turn', or 'both'"
    )
    metric_name: str = Field(
        ..., description="Metric being ranked: 'overall', 'completeness', 'robustness', etc."
    )
    property_type: Optional[str] = Field(
        None, description="Property type filter (e.g., 'reachability')"
    )
    entries: List[LeaderboardEntry] = Field(
        default_factory=list, description="Entries sorted by score (descending)"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When the leaderboard was last updated"
    )

    @field_validator("evaluation_mode")
    @classmethod
    def validate_evaluation_mode(cls, v: str) -> str:
        """Validate that evaluation_mode is one of the allowed values."""
        allowed = {"single_turn", "multi_turn", "both"}
        if v not in allowed:
            raise ValueError(f"evaluation_mode must be one of {allowed}, got '{v}'")
        return v

    def add_entry(self, entry: LeaderboardEntry, keep_newest: bool = True) -> None:
        """
        Add an entry to the leaderboard, maintaining sort order.
        
        If the testee already exists:
        - If keep_newest=True, replace with newer entry (by timestamp)
        - If keep_newest=False, keep existing entry
        
        Args:
            entry: LeaderboardEntry to add
            keep_newest: Whether to keep the newest entry when duplicates exist
        """
        # Check for existing entry from same testee
        existing_idx = None
        for idx, existing in enumerate(self.entries):
            if existing.testee_id == entry.testee_id:
                if existing.model_version == entry.model_version:
                    existing_idx = idx
                    break
        
        if existing_idx is not None:
            existing = self.entries[existing_idx]
            if keep_newest and entry.timestamp > existing.timestamp:
                # Replace with newer entry
                self.entries.pop(existing_idx)
            else:
                # Keep existing entry
                return
        
        # Insert in sorted position (descending by score)
        insert_pos = 0
        for idx, existing in enumerate(self.entries):
            if entry.score > existing.score:
                break
            insert_pos = idx + 1
        
        self.entries.insert(insert_pos, entry)
        self.last_updated = datetime.now(timezone.utc)

    def get_rank(self, testee_id: str, model_version: Optional[str] = None) -> Optional[int]:
        """
        Get the rank (1-indexed) of a testee on this leaderboard.
        
        Args:
            testee_id: Testee identifier
            model_version: Optional model version to match
            
        Returns:
            Rank (1-indexed) or None if not found
        """
        for idx, entry in enumerate(self.entries):
            if entry.testee_id == testee_id:
                if model_version is None or entry.model_version == model_version:
                    return idx + 1
        return None

    def get_top_n(self, n: int = 10) -> List[LeaderboardEntry]:
        """
        Get the top N entries on this leaderboard.
        
        Args:
            n: Number of entries to return
            
        Returns:
            List of top N entries
        """
        return self.entries[:n]


# ============================================================================
# Leaderboard Collection
# ============================================================================


class LeaderboardCollection(BaseModel):
    """
    Container for all leaderboards.
    
    Provides methods for managing multiple leaderboards and
    serialization/deserialization to JSON.
    """

    leaderboards: Dict[str, Leaderboard] = Field(
        default_factory=dict, description="Leaderboards keyed by leaderboard_id"
    )
    version: str = Field("1.0.0", description="Schema version")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When the collection was created"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When any leaderboard was last updated"
    )

    def add_leaderboard(self, leaderboard: Leaderboard) -> None:
        """
        Add a leaderboard to the collection.
        
        Args:
            leaderboard: Leaderboard to add
        """
        self.leaderboards[leaderboard.leaderboard_id] = leaderboard
        self.last_updated = datetime.now(timezone.utc)

    def get_leaderboard(self, leaderboard_id: str) -> Optional[Leaderboard]:
        """
        Get a leaderboard by ID.
        
        Args:
            leaderboard_id: Leaderboard identifier
            
        Returns:
            Leaderboard or None if not found
        """
        return self.leaderboards.get(leaderboard_id)

    def list_leaderboard_ids(self) -> List[str]:
        """
        List all leaderboard IDs in the collection.
        
        Returns:
            List of leaderboard IDs
        """
        return list(self.leaderboards.keys())

    def add_entry(
        self, leaderboard_id: str, entry: LeaderboardEntry, keep_newest: bool = True
    ) -> bool:
        """
        Add an entry to a specific leaderboard.
        
        Args:
            leaderboard_id: Target leaderboard ID
            entry: Entry to add
            keep_newest: Whether to keep the newest entry when duplicates exist
            
        Returns:
            True if entry was added successfully, False if leaderboard not found
        """
        leaderboard = self.get_leaderboard(leaderboard_id)
        if leaderboard is None:
            return False
        leaderboard.add_entry(entry, keep_newest=keep_newest)
        self.last_updated = datetime.now(timezone.utc)
        return True
