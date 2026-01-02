"""
Platform profile management for network benchmark.

Provides platform-specific configurations including container images,
command wrappers, and show commands.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import yaml


@dataclass
class PlatformProfile:
    """Platform-specific configuration profile."""
    
    name: str
    display_name: str
    image: str
    command_wrapper: str
    config_mode: str
    commands: Dict[str, str]


# Default platform profiles (can be overridden by YAML files)
PLATFORM_PROFILES: Dict[str, PlatformProfile] = {
    "frr": PlatformProfile(
        name="frr",
        display_name="FRRouting",
        image="frrouting/frr:latest",
        command_wrapper="vtysh -c '{}'",
        config_mode="configure terminal",
        commands={
            "show_bgp": "show bgp summary json",
            "show_ospf": "show ip ospf neighbor",
            "show_routes": "show ip route json",
            "show_interfaces": "show interface brief",
        }
    ),
    "nokia_srl": PlatformProfile(
        name="nokia_srl",
        display_name="Nokia SR Linux",
        image="ghcr.io/nokia/srlinux:latest",
        command_wrapper="sr_cli '{}'",
        config_mode="enter candidate",
        commands={
            "show_bgp": "show network-instance default protocols bgp neighbor",
            "show_ospf": "show network-instance default protocols ospf neighbor",
            "show_routes": "show network-instance default route-table",
            "show_interfaces": "show interface",
        }
    ),
    "arista_eos": PlatformProfile(
        name="arista_eos",
        display_name="Arista cEOS",
        image="ceos:latest",
        command_wrapper="Cli -c '{}'",
        config_mode="configure",
        commands={
            "show_bgp": "show ip bgp summary | json",
            "show_ospf": "show ip ospf neighbor",
            "show_routes": "show ip route | json",
            "show_interfaces": "show interfaces status",
        }
    ),
    "cisco_ios_xe": PlatformProfile(
        name="cisco_ios_xe",
        display_name="Cisco IOS-XE",
        image="cisco-iosxe:latest",
        command_wrapper="{}",
        config_mode="configure terminal",
        commands={
            "show_bgp": "show ip bgp summary",
            "show_ospf": "show ip ospf neighbor",
            "show_routes": "show ip route",
            "show_interfaces": "show ip interface brief",
        }
    ),
}


def get_platform_profile(platform_name: str) -> Optional[PlatformProfile]:
    """
    Get platform profile by name.
    
    Args:
        platform_name: Platform identifier (e.g., 'frr', 'nokia_srl')
        
    Returns:
        PlatformProfile or None if not found
    """
    return PLATFORM_PROFILES.get(platform_name)


def get_platform_image(platform_name: str) -> str:
    """
    Get container image for a platform.
    
    Args:
        platform_name: Platform identifier
        
    Returns:
        Container image string, defaults to FRR if unknown
    """
    profile = get_platform_profile(platform_name)
    if profile:
        return profile.image
    return PLATFORM_PROFILES["frr"].image


def load_platform_profiles_from_yaml(profiles_dir: Path) -> None:
    """
    Load platform profiles from YAML files.
    
    Args:
        profiles_dir: Directory containing YAML profile files
    """
    if not profiles_dir.exists():
        return
    
    for yaml_file in profiles_dir.glob("*.yaml"):
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)
            
            if data and "name" in data:
                profile = PlatformProfile(
                    name=data["name"],
                    display_name=data.get("display_name", data["name"]),
                    image=data.get("image", ""),
                    command_wrapper=data.get("command_wrapper", "{}"),
                    config_mode=data.get("config_mode", ""),
                    commands=data.get("commands", {}),
                )
                PLATFORM_PROFILES[profile.name] = profile
        except Exception as e:
            print(f"Warning: Failed to load {yaml_file}: {e}")
