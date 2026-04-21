"""
Workshop setup: creates the medallion catalog with external tables.

Reads setup_medallion.sql, replaces placeholders, and executes via
Databricks SQL Statement Execution API.

Usage:
    DATABRICKS_CONFIG_PROFILE=daveok \
    WORKSHOP_STORAGE_ACCOUNT=mystorageaccount \
    WORKSHOP_CONTAINER=medallion \
    WORKSHOP_CATALOG=medallion \
    SOURCE_CATALOG=ot_demo \
    SOURCE_SCHEMA=ot \
    python workshop/run_workshop_setup.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


def main() -> None:
    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "e4082fdb7ea19a15")
    storage_account = os.environ.get("WORKSHOP_STORAGE_ACCOUNT")
    container = os.environ.get("WORKSHOP_CONTAINER", "medallion")
    catalog = os.environ.get("WORKSHOP_CATALOG", "medallion")
    source_catalog = os.environ.get("SOURCE_CATALOG", "ot_demo")
    source_schema = os.environ.get("SOURCE_SCHEMA", "ot")

    if not storage_account:
        print("ERROR: WORKSHOP_STORAGE_ACCOUNT is required (your ADLS account name)")
        sys.exit(1)

    sql_path = Path(__file__).parent / "setup_medallion.sql"
    raw_sql = sql_path.read_text()

    # Replace placeholders
    sql = (
        raw_sql
        .replace("__CATALOG__", catalog)
        .replace("__SOURCE_CATALOG__", source_catalog)
        .replace("__SOURCE_SCHEMA__", source_schema)
        .replace("__STORAGE_ACCOUNT__", storage_account)
        .replace("__CONTAINER__", container)
    )

    # Split into individual statements (skip comments and empty lines)
    statements: list[str] = []
    current: list[str] = []
    for line in sql.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            # Keep comment-only lines out of statements
            if current and not all(l.strip().startswith("--") or l.strip() == "" for l in current):
                current.append(line)
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip()
            if stmt and not all(l.strip().startswith("--") for l in stmt.split("\n")):
                statements.append(stmt)
            current = []

    print(f"Workshop setup: {len(statements)} SQL statements to execute")
    print(f"  Catalog:         {catalog}")
    print(f"  Source:          {source_catalog}.{source_schema}")
    print(f"  Storage:         abfss://{container}@{storage_account}.dfs.core.windows.net/")
    print(f"  Warehouse:       {warehouse_id}")
    print(f"  Profile:         {profile}")
    print()

    w = WorkspaceClient(profile=profile)

    for i, stmt in enumerate(statements, 1):
        # Extract first meaningful line for display
        first_line = next(
            (l.strip() for l in stmt.split("\n") if l.strip() and not l.strip().startswith("--")),
            stmt[:80],
        )
        print(f"[{i}/{len(statements)}] {first_line[:100]}...")

        try:
            result = w.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=stmt,
                wait_timeout="120s",
            )
            if result.status and result.status.state == StatementState.FAILED:
                print(f"  FAILED: {result.status.error}")
                if "already exists" not in str(result.status.error).lower():
                    response = input("  Continue? (y/n): ")
                    if response.lower() != "y":
                        sys.exit(1)
            else:
                print("  OK")
        except Exception as e:
            print(f"  ERROR: {e}")
            response = input("  Continue? (y/n): ")
            if response.lower() != "y":
                sys.exit(1)

    print()
    print("Workshop setup complete!")
    print()
    print("Next steps:")
    print(f"  1. Open Azure portal → Storage → {storage_account} → {container}")
    print("     You should see: bronze/ silver/ gold/ folders")
    print("  2. Open Databricks → Catalog → medallion")
    print("     You should see: bronze, silver, gold schemas")
    print("  3. Open workshop/demo_queries.sql for live demo queries")
    print("  4. Open medallion_architecture_workshop.html for slides")


if __name__ == "__main__":
    main()
