#!/usr/bin/env python3
"""Run test_zerobus.py using credentials from ~/.databrickscfg [agl-demo] (or SP_PROFILE_NAME).

Usage:
  uv run python run_with_profile.py

Requires: [agl-demo] (or SP_PROFILE_NAME) in ~/.databrickscfg with host, client_id, client_secret.
"""

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
    if not host or not client_id or not client_secret:
        print("✗ Missing host, client_id, or client_secret in profile.", file=sys.stderr)
        return 1
    os.environ["DATABRICKS_HOST"] = host
    os.environ["DATABRICKS_CLIENT_ID"] = client_id
    os.environ["DATABRICKS_CLIENT_SECRET"] = client_secret
    if "ZEROBUS_ENDPOINT" not in os.environ:
        wid, reg = os.environ.get("WORKSPACE_ID"), os.environ.get("DATABRICKS_REGION")
        default_ep = f"{wid}.zerobus.{reg}.azuredatabricks.net" if (wid and reg) else "7405607216190670.zerobus.eastus2.azuredatabricks.net"
        os.environ.setdefault("ZEROBUS_ENDPOINT", default_ep)
    if "ZEROBUS_TARGET_TABLE" not in os.environ:
        os.environ.setdefault("ZEROBUS_TARGET_TABLE", "agl_demo.ot.zerobus_test")
    # Defer import so env is set before SDK reads it
    from test_zerobus import main as run_test
    run_test()
    return 0


if __name__ == "__main__":
    sys.exit(main())
