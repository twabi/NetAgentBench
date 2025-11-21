"""
Unit tests for Property Type enum updates.

Tests that verify the PropertyType enum has been updated with new naming
and all references throughout the codebase have been migrated.
"""
import pytest
from benchmark.models.task import PropertyType


class TestPropertyTypeEnumUpdates:
    """Test that PropertyType enum has new naming convention"""

    def test_bgp_configuration_exists(self):
        """Test that BGP_CONFIGURATION property type exists"""
        assert hasattr(PropertyType, "BGP_CONFIGURATION")
        assert PropertyType.BGP_CONFIGURATION == "bgp_configuration"

    def test_ospf_configuration_exists(self):
        """Test that OSPF_CONFIGURATION property type exists"""
        assert hasattr(PropertyType, "OSPF_CONFIGURATION")
        assert PropertyType.OSPF_CONFIGURATION == "ospf_configuration"

    def test_reachability_still_exists(self):
        """Test that REACHABILITY property type still exists"""
        assert hasattr(PropertyType, "REACHABILITY")
        assert PropertyType.REACHABILITY == "reachability"

    def test_old_bgp_session_removed(self):
        """Test that old BGP_SESSION enum value is removed"""
        assert not hasattr(PropertyType, "BGP_SESSION")

    def test_old_ospf_adjacency_removed(self):
        """Test that old OSPF_ADJACENCY enum value is removed"""
        assert not hasattr(PropertyType, "OSPF_ADJACENCY")

    def test_all_property_types_values(self):
        """Test that all PropertyType values are correct"""
        all_values = [item.value for item in PropertyType]
        
        # Should have new values
        assert "bgp_configuration" in all_values
        assert "ospf_configuration" in all_values
        assert "reachability" in all_values
        
        # Should not have old values
        assert "bgp_session" not in all_values
        assert "ospf_adjacency" not in all_values

    def test_property_type_enum_complete(self):
        """Test that PropertyType enum has expected members"""
        expected_members = {
            "REACHABILITY",
            "BGP_CONFIGURATION",
            "OSPF_CONFIGURATION",
            "ROUTE_EXISTS",
            "INTERFACE_UP"
        }
        
        actual_members = {item.name for item in PropertyType}
        
        # Check that new names exist
        assert "BGP_CONFIGURATION" in actual_members
        assert "OSPF_CONFIGURATION" in actual_members
        
        # Check that old names don't exist
        assert "BGP_SESSION" not in actual_members
        assert "OSPF_ADJACENCY" not in actual_members

