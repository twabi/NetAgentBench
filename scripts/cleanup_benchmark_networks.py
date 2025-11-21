#!/usr/bin/env python3
"""
Utility script to clean up all benchmark Docker networks and containers.

This script removes:
- All Docker networks starting with 'bench_'
- All Docker containers starting with 'clab-bench_'
- All Containerlab lab directories

Usage:
    python scripts/cleanup_benchmark_networks.py
"""
import sys
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.infrastructure.containerlab import ContainerlabProvider


def cleanup_all():
    """Clean up all benchmark-related Docker resources."""
    print("=" * 80)
    print("BENCHMARK NETWORK CLEANUP UTILITY")
    print("=" * 80)
    print()
    
    print("This will remove:")
    print("  - All Docker networks starting with 'bench_'")
    print("  - All Docker containers starting with 'clab-bench_'")
    print("  - Containerlab lab files")
    print()
    
    response = input("Continue? (y/N): ").strip().lower()
    if response != 'y':
        print("Cancelled.")
        return
    
    print()
    print("Starting cleanup...")
    print("-" * 80)
    
    # Step 1: Use ContainerlabProvider's built-in cleanup
    print("\n1. Using ContainerlabProvider cleanup...")
    try:
        provider = ContainerlabProvider(cleanup_stale_networks=True)
        print("   ✓ ContainerlabProvider cleanup complete")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Step 2: Force remove any remaining containers
    print("\n2. Force removing any remaining benchmark containers...")
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=clab-bench_", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            container_names = result.stdout.strip().split('\n')
            print(f"   Found {len(container_names)} containers")
            for container_name in container_names:
                try:
                    subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        capture_output=True,
                        timeout=30
                    )
                    print(f"   ✓ Removed: {container_name}")
                except Exception as e:
                    print(f"   ✗ Failed to remove {container_name}: {e}")
        else:
            print("   No containers found")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Step 3: Remove any remaining networks
    print("\n3. Removing any remaining benchmark networks...")
    try:
        result = subprocess.run(
            ["docker", "network", "ls", "--filter", "name=bench_", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            network_names = result.stdout.strip().split('\n')
            print(f"   Found {len(network_names)} networks")
            for network_name in network_names:
                try:
                    subprocess.run(
                        ["docker", "network", "rm", network_name],
                        capture_output=True,
                        timeout=30
                    )
                    print(f"   ✓ Removed: {network_name}")
                except Exception as e:
                    print(f"   ✗ Failed to remove {network_name}: {e}")
        else:
            print("   No networks found")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Step 4: Clean up Containerlab directories
    print("\n4. Cleaning up Containerlab lab directories...")
    try:
        result = subprocess.run(
            ["sudo", "clab", "destroy", "--all", "--cleanup"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            print("   ✓ Containerlab cleanup complete")
        else:
            print(f"   ⚠️  Containerlab cleanup returned code {result.returncode}")
    except Exception as e:
        print(f"   ⚠️  Containerlab cleanup not available: {e}")
    
    print()
    print("-" * 80)
    print("Cleanup complete!")
    print()
    
    # Show remaining resources
    print("Checking for any remaining benchmark resources...")
    try:
        # Check containers
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=clab-bench_", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        remaining_containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Check networks
        result = subprocess.run(
            ["docker", "network", "ls", "--filter", "name=bench_", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        remaining_networks = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        if remaining_containers:
            print(f"⚠️  {len(remaining_containers)} container(s) still remain:")
            for name in remaining_containers:
                print(f"   - {name}")
        else:
            print("✓ No containers remaining")
        
        if remaining_networks:
            print(f"⚠️  {len(remaining_networks)} network(s) still remain:")
            for name in remaining_networks:
                print(f"   - {name}")
        else:
            print("✓ No networks remaining")
            
    except Exception as e:
        print(f"Could not check remaining resources: {e}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        cleanup_all()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

