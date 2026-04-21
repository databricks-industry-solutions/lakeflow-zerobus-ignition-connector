#!/usr/bin/env python3
"""Validate AGL Tomago BESS example setup is complete.

This script verifies all required files exist and are properly configured.

Usage:
    python validate_setup.py
"""

import json
import sys
from pathlib import Path


def check_file_exists(filepath: Path, description: str) -> bool:
    """Check if a file exists and report status."""
    exists = filepath.exists()
    status = "✓" if exists else "✗"
    print(f"  {status} {description}: {filepath.name}")
    return exists


def check_json_valid(filepath: Path) -> bool:
    """Check if a JSON file is valid."""
    try:
        with open(filepath) as f:
            json.load(f)
        return True
    except (json.JSONDecodeError, FileNotFoundError):
        return False


def count_tags_in_json(filepath: Path) -> int:
    """Count AtomicTag entries in a tag JSON file."""
    def _count(obj: dict, count: int = 0) -> int:
        if obj.get("tagType") == "AtomicTag":
            return count + 1
        for child in obj.get("tags", []):
            count = _count(child, count)
        return count

    with open(filepath) as f:
        data = json.load(f)
    return _count(data)


def main():
    script_dir = Path(__file__).parent
    sql_dir = script_dir.parent.parent / "pipelines" / "sites" / "agl_tomago"

    print("=" * 60)
    print("AGL Tomago BESS Example - Setup Validation")
    print("=" * 60)

    all_ok = True

    # Check tag JSON files
    print("\n1. Tag JSON Files:")
    tag_files = [
        ("agl_bess_tomago_site01_tags.json", "BESS telemetry tags"),
        ("agl_grid_tomago_site01_tags.json", "Grid/dispatch tags"),
        ("agl_market_tomago_site01_tags.json", "Market data tags"),
        ("agl_cmms_tomago_site01_tags.json", "CMMS/maintenance tags"),
    ]

    total_tags = 0
    for filename, desc in tag_files:
        filepath = script_dir / filename
        if check_file_exists(filepath, desc):
            if check_json_valid(filepath):
                tag_count = count_tags_in_json(filepath)
                total_tags += tag_count
                print(f"      ({tag_count} tags)")
            else:
                print("      (invalid JSON!)")
                all_ok = False
        else:
            all_ok = False

    print(f"\n   Total tags: {total_tags}")

    # Check timer scripts
    print("\n2. Timer Scripts:")
    timer_scripts = [
        ("timer_script_agl_bess_tomago_site01.py", "BESS simulation (1s)"),
        ("timer_script_agl_grid_tomago_site01.py", "Grid simulation (1s)"),
        ("timer_script_agl_market_tomago_site01.py", "Market simulation (2s)"),
        ("timer_script_agl_cmms_tomago_site01.py", "CMMS simulation (10s)"),
    ]

    for filename, desc in timer_scripts:
        if not check_file_exists(script_dir / filename, desc):
            all_ok = False

    # Check SQL files
    print("\n3. SQL Setup Files:")
    sql_files = [
        ("10_silver_scaffolding.sql", "Schema + tables"),
        ("11_seed_tomago_site01_mapping.sql", "Signal mappings"),
        ("20_silver_views.sql", "Silver views"),
        ("25_bridge_to_prd_schema.sql", "PRD schema bridge"),
        ("30_gold_views.sql", "Gold views"),
    ]

    for filename, desc in sql_files:
        if not check_file_exists(sql_dir / filename, desc):
            all_ok = False

    # Check helper scripts
    print("\n4. Helper Scripts:")
    helper_files = [
        ("push_tags_to_ignition.py", "Ignition automation"),
        ("README.md", "Documentation"),
    ]

    for filename, desc in helper_files:
        if not check_file_exists(script_dir / filename, desc):
            all_ok = False

    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ All files present and valid!")
        print("\nNext steps:")
        print("  1. Set up Ignition Gateway with tag providers")
        print("  2. Run SQL setup scripts in Databricks")
        print("  3. Configure Zerobus connector")
        print("\nSee README.md for detailed instructions.")
        return 0
    else:
        print("✗ Some files are missing or invalid!")
        print("  Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
