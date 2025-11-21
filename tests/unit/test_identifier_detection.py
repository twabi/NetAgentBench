"""
Unit tests for identifier detection system.

Tests auto-detection of analysis type from identifier strings.
"""
import pytest
import tempfile
from pathlib import Path

from benchmark.analysis.identifier import IdentifierDetector, AnalysisSpec
from benchmark.storage import ResultsStorage
from benchmark.models.results import (
    BenchmarkResult,
    ScoringResult,
    ValidityCheck,
    ExecutionMetrics,
)
from datetime import datetime


@pytest.fixture
def temp_storage():
    """Create temporary storage with sample data"""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = ResultsStorage(base_dir=temp_dir)
        
        # Create sample result
        result = BenchmarkResult(
            run_id="run1",
            timestamp=datetime.now(),
            task_id="reachability_task_1",
            testee_id="gpt-4",
            testee_type="llm",
            success=True,
            property_results=[],
            scoring=ScoringResult(
                completeness=0.8,
                robustness=0.7,
                syntactic_validity=0.9,
                efficiency=None,
                final_score=0.8,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=40.0,
                config_execution_time=10.0,
                convergence_time=30.0,
                evaluation_time=5.0,
                total_time=85.0,
            ),
            execution_log=[],
            errors=[],
        )
        storage.save_result(result)
        
        # Create sample analysis file
        analysis_dir = Path(temp_dir) / "analysis"
        analysis_dir.mkdir(exist_ok=True)
        analysis_file = analysis_dir / "study_2024.json"
        analysis_file.write_text('{"analysis_id": "study_2024"}')
        
        yield storage


class TestIdentifierDetector:
    """Test IdentifierDetector class"""

    def test_initialization(self, temp_storage):
        """Test creating IdentifierDetector"""
        detector = IdentifierDetector(temp_storage)
        assert detector is not None
        assert detector.storage == temp_storage

    def test_detect_comparison(self, temp_storage):
        """Test detecting comparison identifiers (comma-separated)"""
        detector = IdentifierDetector(temp_storage)
        
        # Two testees
        spec = detector.detect("gpt-4,baseline")
        assert spec.analysis_type == "comparison"
        assert spec.testees == ["gpt-4", "baseline"]
        assert spec.testee_id is None
        assert spec.property_type is None
        
        # Three testees
        spec = detector.detect("gpt-4,claude,baseline")
        assert spec.analysis_type == "comparison"
        assert len(spec.testees) == 3
        assert "gpt-4" in spec.testees
        assert "claude" in spec.testees
        assert "baseline" in spec.testees

    def test_detect_property_type(self, temp_storage):
        """Test detecting property type identifiers"""
        detector = IdentifierDetector(temp_storage)
        
        # Valid property types
        for prop_type in ["reachability", "bgp_configuration", "ospf_configuration"]:
            spec = detector.detect(prop_type)
            assert spec.analysis_type == "property"
            assert spec.property_type == prop_type
            assert spec.testee_id is None
            assert spec.testees is None

    def test_detect_testee_id(self, temp_storage):
        """Test detecting testee ID"""
        detector = IdentifierDetector(temp_storage)
        
        # Should treat non-property, non-comma-separated strings as testee IDs
        spec = detector.detect("gpt-4")
        assert spec.analysis_type == "testee"
        assert spec.testee_id == "gpt-4"
        assert spec.property_type is None
        assert spec.testees is None

    def test_detect_with_whitespace(self, temp_storage):
        """Test detection with whitespace in identifiers"""
        detector = IdentifierDetector(temp_storage)
        
        # Should strip whitespace
        spec = detector.detect(" gpt-4 , baseline ")
        assert spec.analysis_type == "comparison"
        assert "gpt-4" in spec.testees
        assert "baseline" in spec.testees
        
        spec = detector.detect("  reachability  ")
        assert spec.analysis_type == "property"
        assert spec.property_type == "reachability"

    def test_detect_case_insensitive(self, temp_storage):
        """Test case-insensitive property type detection"""
        detector = IdentifierDetector(temp_storage)
        
        # Property types should be case-insensitive
        spec = detector.detect("REACHABILITY")
        assert spec.analysis_type == "property"
        assert spec.property_type == "reachability"
        
        spec = detector.detect("Bgp_Configuration")
        assert spec.analysis_type == "property"
        assert spec.property_type == "bgp_configuration"

    def test_single_testee_not_comparison(self, temp_storage):
        """Test that single testee is not treated as comparison"""
        detector = IdentifierDetector(temp_storage)
        
        # Single item should be testee, not comparison
        spec = detector.detect("gpt-4,")  # Trailing comma
        assert spec.analysis_type == "testee"
        assert spec.testee_id == "gpt-4"

    def test_empty_identifier(self, temp_storage):
        """Test handling of empty identifier"""
        detector = IdentifierDetector(temp_storage)
        
        with pytest.raises(ValueError):
            detector.detect("")

    def test_property_type_priority(self, temp_storage):
        """Test that property types are detected before testee IDs"""
        detector = IdentifierDetector(temp_storage)
        
        # If identifier matches property type, should be treated as property
        spec = detector.detect("reachability")
        assert spec.analysis_type == "property"
        assert spec.property_type == "reachability"
        
        # Not a testee named "reachability"
        assert spec.testee_id is None


class TestAnalysisSpec:
    """Test AnalysisSpec model"""

    def test_create_testee_spec(self):
        """Test creating testee analysis spec"""
        spec = AnalysisSpec(
            analysis_type="testee",
            testee_id="gpt-4",
            property_type=None,
            testees=None,
        )
        assert spec.analysis_type == "testee"
        assert spec.testee_id == "gpt-4"
        assert spec.property_type is None
        assert spec.testees is None

    def test_create_comparison_spec(self):
        """Test creating comparison analysis spec"""
        spec = AnalysisSpec(
            analysis_type="comparison",
            testee_id=None,
            property_type=None,
            testees=["gpt-4", "baseline"],
        )
        assert spec.analysis_type == "comparison"
        assert spec.testees == ["gpt-4", "baseline"]
        assert spec.testee_id is None
        assert spec.property_type is None

    def test_create_property_spec(self):
        """Test creating property analysis spec"""
        spec = AnalysisSpec(
            analysis_type="property",
            testee_id=None,
            property_type="reachability",
            testees=None,
        )
        assert spec.analysis_type == "property"
        assert spec.property_type == "reachability"
        assert spec.testee_id is None
        assert spec.testees is None


class TestEdgeCases:
    """Test edge cases in identifier detection"""

    def test_numeric_testee_id(self, temp_storage):
        """Test numeric testee identifiers"""
        detector = IdentifierDetector(temp_storage)
        
        spec = detector.detect("123")
        assert spec.analysis_type == "testee"
        assert spec.testee_id == "123"

    def test_special_characters_in_testee(self, temp_storage):
        """Test testee IDs with special characters"""
        detector = IdentifierDetector(temp_storage)
        
        spec = detector.detect("gpt-4-turbo")
        assert spec.analysis_type == "testee"
        assert spec.testee_id == "gpt-4-turbo"
        
        spec = detector.detect("model_v1.2")
        assert spec.analysis_type == "testee"
        assert spec.testee_id == "model_v1.2"

    def test_mixed_case_comparison(self, temp_storage):
        """Test comparison with mixed case testee IDs"""
        detector = IdentifierDetector(temp_storage)
        
        spec = detector.detect("GPT-4,Baseline")
        assert spec.analysis_type == "comparison"
        assert "GPT-4" in spec.testees
        assert "Baseline" in spec.testees

    def test_property_substring_match(self, temp_storage):
        """Test that property type detection is not substring-based"""
        detector = IdentifierDetector(temp_storage)
        
        # "reach" is not a property type (substring of "reachability")
        spec = detector.detect("reach")
        assert spec.analysis_type == "testee"  # Should be treated as testee
        assert spec.testee_id == "reach"

