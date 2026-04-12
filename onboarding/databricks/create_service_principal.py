#!/usr/bin/env python3
"""Create a Databricks service principal with OAuth M2M credentials.

Automates the SP lifecycle:
  1. Creates (or finds) a service principal at the account level
  2. Assigns it to the target workspace
  3. Generates an OAuth client secret
  4. Writes the profile to ~/.databrickscfg

UC grants are applied by db-setup-sql (after catalog/schema exist). Run make db-setup-sql
to create the catalog and apply SP grants.

Requires:
  - An account-level profile in ~/.databrickscfg (e.g. ACCOUNT-<uuid>)
  - A workspace-level profile for resolving host (e.g. daveok)
  - databricks-sdk

Usage:
  uv run --with databricks-sdk python onboarding/databricks/create_service_principal.py

  # Custom SP name + profile name
  uv run --with databricks-sdk python onboarding/databricks/create_service_principal.py \
    --sp-name my-connector-sp --profile-name my-sp-profile
"""

from __future__ import annotations

import argparse
import configparser
import os
import re
import sys
from pathlib import Path

from databricks.sdk import AccountClient
from databricks.sdk.service.iam import WorkspacePermission

DATABRICKSCFG = Path.home() / ".databrickscfg"

DEFAULT_SP_NAME = "ignition-zerobus-agl"
DEFAULT_PROFILE_NAME = "agl-demo"
DEFAULT_WORKSPACE_PROFILE = "daveok"
DEFAULT_CATALOG = "agl_demo"
DEFAULT_SCHEMA = "ot"
DEFAULT_WAREHOUSE_ID = "e4082fdb7ea19a15"


# ── helpers ──────────────────────────────────────────────────


def find_account_profile() -> str | None:
    """Return the first ACCOUNT-* profile in ~/.databrickscfg."""
    cfg = configparser.ConfigParser()
    cfg.read(DATABRICKSCFG)
    for section in cfg.sections():
        if section.startswith("ACCOUNT-"):
            return section
    return None


def extract_workspace_id(host: str) -> int:
    """Extract the workspace ID from a host URL (adb-<id>...)."""
    m = re.search(r"adb-(\d+)", host)
    if m:
        return int(m.group(1))
    raise ValueError(f"Cannot extract workspace ID from host: {host}")


def get_workspace_host(profile: str) -> str:
    """Read the host value for a profile in ~/.databrickscfg."""
    cfg = configparser.ConfigParser()
    cfg.read(DATABRICKSCFG)
    host = cfg.get(profile, "host", fallback=None)
    if not host:
        raise ValueError(f"Profile [{profile}] has no 'host' in {DATABRICKSCFG}")
    return host


def find_existing_sp(a: AccountClient, display_name: str):
    """Find an existing account-level SP by display name."""
    for sp in a.service_principals.list(filter=f'displayName eq "{display_name}"'):
        return sp
    return None


def write_profile(profile_name: str, host: str, client_id: str, client_secret: str) -> None:
    """Write (or overwrite) an oauth-m2m profile in ~/.databrickscfg.

    Uses regex replacement to avoid reformatting the rest of the file.
    """
    content = DATABRICKSCFG.read_text() if DATABRICKSCFG.exists() else ""

    new_block = (
        f"[{profile_name}]\n"
        f"host          = {host}\n"
        f"client_id     = {client_id}\n"
        f"client_secret = {client_secret}\n"
        f"auth_type     = oauth-m2m\n"
    )

    # Replace existing profile block (up to next [section] or EOF)
    pattern = rf"^\[{re.escape(profile_name)}\].*?(?=^\[|\Z)"
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        content = re.sub(pattern, new_block, content, count=1, flags=re.MULTILINE | re.DOTALL)
    else:
        content = content.rstrip() + "\n\n" + new_block

    DATABRICKSCFG.write_text(content)


# ── main ─────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a Databricks service principal with OAuth M2M credentials"
    )
    parser.add_argument(
        "--sp-name",
        default=os.environ.get("SP_NAME", DEFAULT_SP_NAME),
        help=f"SP display name (default: {DEFAULT_SP_NAME})",
    )
    parser.add_argument(
        "--profile-name",
        default=os.environ.get("SP_PROFILE_NAME", DEFAULT_PROFILE_NAME),
        help=f"Profile name to write in ~/.databrickscfg (default: {DEFAULT_PROFILE_NAME})",
    )
    parser.add_argument(
        "--account-profile",
        default=os.environ.get("ACCOUNT_PROFILE"),
        help="Account-level profile in ~/.databrickscfg (auto-detected if not set)",
    )
    parser.add_argument(
        "--workspace-profile",
        default=os.environ.get("DATABRICKS_CONFIG_PROFILE", DEFAULT_WORKSPACE_PROFILE),
        help=f"Workspace profile for resolving workspace host (default: {DEFAULT_WORKSPACE_PROFILE})",
    )
    args = parser.parse_args()

    # ── resolve profiles ──

    account_profile = args.account_profile or find_account_profile()
    if not account_profile:
        print(
            "✘ No ACCOUNT-* profile found in ~/.databrickscfg.\n"
            "  Create one with:\n"
            "    databricks auth login --host https://accounts.azuredatabricks.net --account-id <your-account-id>",
            file=sys.stderr,
        )
        return 1

    ws_host = get_workspace_host(args.workspace_profile)
    workspace_id = extract_workspace_id(ws_host)

    print(f"  Account profile:   [{account_profile}]")
    print(f"  Workspace profile: [{args.workspace_profile}] -> {ws_host}")
    print(f"  Workspace ID:      {workspace_id}")
    print(f"  SP display name:   {args.sp_name}")
    print(f"  Target profile:    [{args.profile_name}]")
    print()

    # ── step 1: connect to account ──

    print("▸ Step 1: Connecting to Databricks account...")
    try:
        a = AccountClient(profile=account_profile)
        sp = find_existing_sp(a, args.sp_name)
    except Exception as e:
        account_id = account_profile.replace("ACCOUNT-", "") if account_profile.startswith("ACCOUNT-") else "<account-id>"
        print(
            f"✘ Account auth failed for [{account_profile}]: {e}\n"
            "  If you recently re-authenticated, the CLI token cache may be stale. Clear it:\n"
            "    make db-clear-account-cache\n"
            "  Then re-authenticate at the account level:\n"
            f"    databricks auth login --host https://accounts.azuredatabricks.net --account-id {account_id}\n"
            "  Then run: make db-create-sp",
            file=sys.stderr,
        )
        return 1

    # ── step 2: create or find SP (we have sp from above, or need to create) ──

    print("▸ Step 2: Creating service principal...")
    if sp:
        print(f"  Found existing SP: id={sp.id}  application_id={sp.application_id}")
    else:
        sp = a.service_principals.create(display_name=args.sp_name, active=True)
        print(f"  Created SP: id={sp.id}  application_id={sp.application_id}")

    # ── step 3: assign to workspace ──

    print(f"▸ Step 3: Assigning SP to workspace {workspace_id}...")
    try:
        a.workspace_assignment.update(
            workspace_id=workspace_id,
            principal_id=sp.id,
            permissions=[WorkspacePermission.USER],
        )
        print("  Assigned.")
    except Exception as e:
        err = str(e).lower()
        if "already exists" in err or "already_exists" in err or "already assigned" in err:
            print("  Already assigned.")
        else:
            # Non-fatal — SP might still work if already in workspace via SCIM sync
            print(f"  WARN: {e}")

    # ── step 4: generate OAuth secret ──

    print("▸ Step 4: Generating OAuth client secret...")
    # SPs are limited to 5 OAuth secrets; delete oldest if at limit so we can create one
    MAX_SP_SECRETS = 5
    existing = list(a.service_principal_secrets.list(service_principal_id=sp.id))
    if len(existing) >= MAX_SP_SECRETS:
        # Sort by create_time (oldest first), delete until we have room for one more
        existing.sort(key=lambda s: (s.create_time or "") or "z")
        to_remove = len(existing) - (MAX_SP_SECRETS - 1)
        for secret in existing[:to_remove]:
            if secret.id:
                print(f"  Removing old secret (id={secret.id[:8]}...) to make space...")
                a.service_principal_secrets.delete(service_principal_id=sp.id, secret_id=secret.id)
    secret_resp = a.service_principal_secrets.create(service_principal_id=sp.id)
    client_id = sp.application_id
    client_secret = secret_resp.secret

    if not client_secret:
        print("✘ No secret returned. Check account-level permissions.", file=sys.stderr)
        return 1

    masked = f"{client_secret[:8]}...{client_secret[-4:]}"
    print(f"  client_id:     {client_id}")
    print(f"  client_secret: {masked}")

    # ── step 5: write profile ──

    print(f"▸ Step 5: Writing profile [{args.profile_name}] to {DATABRICKSCFG}...")
    write_profile(args.profile_name, ws_host, client_id, client_secret)
    print(f"  Done. Verify with: databricks auth env --profile {args.profile_name}")

    # Grants are applied by db-setup-sql (after catalog/schema exist). See setup_databricks.sql.

    # ── summary ──

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  SP Name:         {args.sp_name}")
    print(f"  Application ID:  {client_id}")
    print(f"  Profile:         [{args.profile_name}] in {DATABRICKSCFG}")
    print(f"  Workspace:       {ws_host}")
    print()
    print("  Test auth:    databricks auth env --profile " + args.profile_name)
    print("  Create catalog + apply grants:  make db-setup-sql DATABRICKS_CONFIG_PROFILE=" + args.workspace_profile)
    print("  Use in Make:  make configure-83 DATABRICKS_CONFIG_PROFILE=" + args.profile_name)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return 0


if __name__ == "__main__":
    sys.exit(main())
