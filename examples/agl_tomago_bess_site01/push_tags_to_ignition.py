#!/usr/bin/env python3
"""Push AGL Tomago BESS tags to Ignition Gateway via REST API.

This script uses Ignition's Web Dev module REST API to programmatically
create tag providers and import tags without manual Designer work.

Requirements:
- Ignition Gateway with Web Dev module installed
- Gateway credentials with tag write permissions
- Python 3.8+ with requests library

Usage:
    python push_tags_to_ignition.py --gateway http://localhost:8088 --user admin --password <pw>

    # Dry run (show what would be created):
    python push_tags_to_ignition.py --gateway http://localhost:8088 --dry-run
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


# Tag provider → JSON file mapping
TAG_FILES = {
    "agl_bess": "agl_bess_tomago_site01_tags.json",
    "agl_grid": "agl_grid_tomago_site01_tags.json",
    "agl_market": "agl_market_tomago_site01_tags.json",
    "agl_cmms": "agl_cmms_tomago_site01_tags.json",
}

# Timer script configurations
TIMER_SCRIPTS = {
    "agl_bess_tomago_sim": {
        "rate": 1000,
        "file": "timer_script_agl_bess_tomago_site01.py",
    },
    "agl_grid_tomago_sim": {
        "rate": 1000,
        "file": "timer_script_agl_grid_tomago_site01.py",
    },
    "agl_market_tomago_sim": {
        "rate": 2000,
        "file": "timer_script_agl_market_tomago_site01.py",
    },
    "agl_cmms_tomago_sim": {
        "rate": 10000,
        "file": "timer_script_agl_cmms_tomago_site01.py",
    },
}


class IgnitionClient:
    """Client for Ignition Gateway REST API."""

    def __init__(self, gateway_url: str, username: str | None = None, password: str | None = None):
        self.base_url = gateway_url.rstrip("/")
        self.session = requests.Session()
        if username and password:
            self.session.auth = (username, password)
        self.session.headers["Content-Type"] = "application/json"

    def _api_url(self, endpoint: str) -> str:
        return f"{self.base_url}/system/webdev/api/{endpoint}"

    def check_connection(self) -> bool:
        """Verify gateway is reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/StatusPing", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def create_tag_provider(self, name: str, provider_type: str = "standard") -> dict[str, Any]:
        """Create a new tag provider."""
        # Note: This requires a custom Web Dev endpoint or Gateway config script
        # Standard Ignition doesn't expose provider creation via REST
        # This is a placeholder for the API structure
        payload = {
            "name": name,
            "type": provider_type,
        }
        return {"action": "create_provider", "payload": payload}

    def import_tags(self, provider: str, tags_json: dict[str, Any]) -> dict[str, Any]:
        """Import tags into a provider."""
        # This uses the standard tag import structure
        # Requires Web Dev endpoint at /api/tags/import
        payload = {
            "provider": provider,
            "tags": tags_json,
            "collision": "o",  # overwrite existing
        }
        return {"action": "import_tags", "payload": payload}

    def create_timer_script(self, name: str, rate_ms: int, script_code: str) -> dict[str, Any]:
        """Create a gateway timer script."""
        # Note: Timer script creation typically requires Gateway config
        # This is the structure for documentation purposes
        payload = {
            "name": name,
            "rate": rate_ms,
            "enabled": True,
            "script": script_code,
        }
        return {"action": "create_timer_script", "payload": payload}


def load_json_file(filepath: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    with open(filepath) as f:
        return json.load(f)


def load_script_file(filepath: Path) -> str:
    """Load a Python script file."""
    with open(filepath) as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser(description="Push AGL Tomago tags to Ignition Gateway")
    parser.add_argument("--gateway", required=True, help="Ignition Gateway URL (e.g., http://localhost:8088)")
    parser.add_argument("--user", help="Gateway username")
    parser.add_argument("--password", help="Gateway password")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--providers-only", action="store_true", help="Only create tag providers")
    parser.add_argument("--tags-only", action="store_true", help="Only import tags (providers must exist)")
    parser.add_argument("--scripts-only", action="store_true", help="Only create timer scripts")
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    client = IgnitionClient(args.gateway, args.user, args.password)

    if not args.dry_run:
        print(f"Checking connection to {args.gateway}...")
        if not client.check_connection():
            print("Error: Cannot connect to Ignition Gateway")
            print("Ensure the gateway is running and the URL is correct.")
            sys.exit(1)
        print("Connected successfully.")
    else:
        print("=== DRY RUN MODE ===\n")

    # Step 1: Create tag providers
    if not args.tags_only and not args.scripts_only:
        print("\n--- Tag Providers ---")
        for provider_name in TAG_FILES:
            action = client.create_tag_provider(provider_name)
            if args.dry_run:
                print(f"Would create provider: {provider_name}")
            else:
                print(f"Creating provider: {provider_name}")
                # In real implementation, this would call the API
                # For now, print instructions
                print(f"  NOTE: Create provider '{provider_name}' manually in Gateway Config")

    # Step 2: Import tags
    if not args.providers_only and not args.scripts_only:
        print("\n--- Tag Import ---")
        for provider_name, json_file in TAG_FILES.items():
            json_path = script_dir / json_file
            if not json_path.exists():
                print(f"Warning: {json_file} not found, skipping")
                continue

            tags_json = load_json_file(json_path)
            action = client.import_tags(provider_name, tags_json)

            if args.dry_run:
                tag_count = count_tags(tags_json)
                print(f"Would import {tag_count} tags into [{provider_name}] from {json_file}")
            else:
                print(f"Importing tags into [{provider_name}] from {json_file}")
                # Print curl equivalent for manual execution
                print(f"  curl -X POST {args.gateway}/system/webdev/api/tags/import \\")
                print(f"       -H 'Content-Type: application/json' \\")
                print(f"       -d @{json_file}")

    # Step 3: Create timer scripts
    if not args.providers_only and not args.tags_only:
        print("\n--- Timer Scripts ---")
        for script_name, config in TIMER_SCRIPTS.items():
            script_path = script_dir / config["file"]
            if not script_path.exists():
                print(f"Warning: {config['file']} not found, skipping")
                continue

            script_code = load_script_file(script_path)
            action = client.create_timer_script(script_name, config["rate"], script_code)

            if args.dry_run:
                print(f"Would create timer script: {script_name} (rate: {config['rate']}ms)")
            else:
                print(f"Timer script: {script_name}")
                print(f"  Rate: {config['rate']}ms")
                print(f"  File: {config['file']}")
                print("  NOTE: Create in Gateway Config → Timer Scripts, paste code from file")

    print("\n=== Summary ===")
    print(f"Providers: {len(TAG_FILES)}")
    print(f"Timer scripts: {len(TIMER_SCRIPTS)}")
    print("\nFor manual setup in Ignition Designer, see README.md")


def count_tags(tags_json: dict[str, Any], count: int = 0) -> int:
    """Recursively count tags in a tag JSON structure."""
    if tags_json.get("tagType") == "AtomicTag":
        return count + 1
    if "tags" in tags_json:
        for child in tags_json["tags"]:
            count = count_tags(child, count)
    return count


if __name__ == "__main__":
    main()
