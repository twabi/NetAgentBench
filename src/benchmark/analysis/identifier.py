"""
Identifier detection for analysis system.

Auto-detects the type of analysis to perform based on the identifier string.
"""
from typing import Optional, List
from pydantic import BaseModel, Field

from benchmark.storage import ResultsStorage


# Valid property types (from task repository)
VALID_PROPERTY_TYPES = [
    "reachability",
    "bgp_configuration",
    "ospf_configuration",
]


class AnalysisSpec(BaseModel):
    """Specification for what type of analysis to run"""

    analysis_type: str = Field(
        ..., description="Type of analysis: 'testee', 'comparison', or 'property'"
    )
    testee_id: Optional[str] = Field(
        None, description="Testee ID (for testee analysis)"
    )
    property_type: Optional[str] = Field(
        None, description="Property type (for property analysis)"
    )
    testees: Optional[List[str]] = Field(
        None, description="List of testee IDs (for comparison analysis)"
    )


class IdentifierDetector:
    """Detect identifier type and extract analysis parameters"""

    def __init__(self, storage: ResultsStorage):
        """
        Initialize IdentifierDetector.

        Args:
            storage: ResultsStorage instance for checking existing data
        """
        self.storage = storage

    def detect(self, identifier: str) -> AnalysisSpec:
        """
        Auto-detect what type of analysis to run.

        Detection priority:
        1. Check if comma-separated (comparison)
        2. Check if valid property_type
        3. Otherwise treat as testee_id

        Examples:
        - "gpt-4" -> testee_id -> TesteeAnalysis
        - "gpt-4,claude,baseline" -> comparison -> ComparisonAnalysis
        - "reachability" -> property_type -> PropertyAnalysis

        Args:
            identifier: String identifier to detect

        Returns:
            AnalysisSpec with (analysis_type, parameters)

        Raises:
            ValueError: If identifier is empty or invalid
        """
        if not identifier or not identifier.strip():
            raise ValueError("Identifier cannot be empty")

        identifier = identifier.strip()

        # 1. Check if comma-separated (comparison)
        if "," in identifier:
            testees = [t.strip() for t in identifier.split(",") if t.strip()]
            
            if len(testees) < 2:
                # Only one testee after filtering, treat as single testee
                return AnalysisSpec(
                    analysis_type="testee",
                    testee_id=testees[0] if testees else identifier,
                    property_type=None,
                    testees=None,
                )
            
            return AnalysisSpec(
                analysis_type="comparison",
                testee_id=None,
                property_type=None,
                testees=testees,
            )

        # 2. Check if valid property_type (case-insensitive)
        identifier_lower = identifier.lower()
        if identifier_lower in VALID_PROPERTY_TYPES:
            return AnalysisSpec(
                analysis_type="property",
                testee_id=None,
                property_type=identifier_lower,
                testees=None,
            )

        # 3. Otherwise treat as testee_id
        return AnalysisSpec(
            analysis_type="testee",
            testee_id=identifier,
            property_type=None,
            testees=None,
        )

