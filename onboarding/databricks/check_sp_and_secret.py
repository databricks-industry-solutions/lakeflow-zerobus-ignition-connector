#!/usr/bin/env python3
"""Check that the connector SP profile exists and the OAuth secret works.

Reads ~/.databrickscfg [agl-demo] (or SP_PROFILE_NAME), prints host + client_id,
verifies client_secret by obtaining a token (WorkspaceClient call). Use this
before configure-83 to confirm the gateway will get valid credentials.

Usage:
  uv run --with databricks-sdk python onboarding/databricks/check_sp_and_secret.py
  SP_PROFILE_NAME=agl-demo uv run --with databricks-sdk python onboarding/databricks/check_sp_and_secret.py
"""

from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path

DATABRICKSCFG = Path.home() / ".databrickscfg"
DEFAULT_PROFILE = "agl-demo"


def main() -> int:
    profile_name = os.environ.get("SP_PROFILE_NAME", DEFAULT_PROFILE)

    if not DATABRICKSCFG.exists():
        print(f"✗ {DATABRICKSCFG} not found.", file=sys.stderr)
        return 1

    cfg = configparser.ConfigParser()
    cfg.read(DATABRICKSCFG)

    if profile_name not in cfg:
        print(f"✗ Profile [{profile_name}] not found in {DATABRICKSCFG}", file=sys.stderr)
        return 1

    section = cfg[profile_name]
    host = section.get("host", "").strip()
    client_id = section.get("client_id", "").strip()
    client_secret = section.get("client_secret", "").strip()

    print(f"Profile: [{profile_name}] in {DATABRICKSCFG}")
    print(f"  host:         {host or '(missing)'}")
    print(f"  client_id:    {client_id or '(missing)'}")
    print(f"  client_secret: {'set (' + str(len(client_secret)) + ' chars)' if client_secret else '(missing)'}")

    if not host or not client_id or not client_secret:
        print("✗ Missing host, client_id, or client_secret. Run make db-create-sp or set them manually.", file=sys.stderr)
        return 1

    # Verify secret works by calling the workspace as the SP
    print("\nVerifying OAuth secret (calling workspace as SP)...")
    try:
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient(profile=profile_name)
        # Minimal call that requires a valid token
        w.current_user.me()
        print("✔ SP credentials valid (token obtained, current_user succeeded).")
    except Exception as e:
        print(f"✗ SP credentials invalid or insufficient: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
