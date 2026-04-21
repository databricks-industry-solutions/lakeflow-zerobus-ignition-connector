"""Lakebase PostgreSQL role and grant helpers.

Helpers are intentionally idempotent to support repeatable direct deployments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import psycopg
from psycopg import sql


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def connect_postgres(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
) -> psycopg.Connection:
    return psycopg.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password,
        sslmode="require",
        autocommit=True,
    )


def ensure_database(conn: psycopg.Connection, database_name: str) -> bool:
    """Ensure database exists. Returns True if created."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
        if cur.fetchone():
            return False
        cur.execute(f"CREATE DATABASE {_quote_ident(database_name)}")
        return True


def ensure_login_role(conn: psycopg.Connection, role_name: str, password: str) -> bool:
    """Create role if missing and rotate password. Returns True if created."""
    created = False
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,))
        if not cur.fetchone():
            cur.execute(f"CREATE ROLE {_quote_ident(role_name)} LOGIN")
            created = True
        # PostgreSQL does not support bind parameters in ALTER ROLE PASSWORD;
        # use a safely-quoted SQL literal for rotation.
        cur.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role_name),
                sql.Literal(password),
            )
        )
    return created


def _execute_sql_statements(conn: psycopg.Connection, statements: Iterable[str]) -> None:
    with conn.cursor() as cur:
        for stmt in statements:
            sql = stmt.strip()
            if sql:
                cur.execute(sql)


def apply_sql_file(conn: psycopg.Connection, sql_path: Path) -> None:
    """Apply semicolon-delimited SQL file statements in order."""
    text = sql_path.read_text()
    parts = [p.strip() for p in text.split(";")]
    _execute_sql_statements(conn, parts)


def grant_connector_privileges(
    conn: psycopg.Connection,
    *,
    role_name: str,
    schema_name: str,
    table_name: str,
) -> None:
    qrole = _quote_ident(role_name)
    qschema = _quote_ident(schema_name)
    qtable = _quote_ident(table_name)
    with conn.cursor() as cur:
        cur.execute(f"GRANT USAGE ON SCHEMA {qschema} TO {qrole}")
        cur.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {qschema}.{qtable} TO {qrole}")
        cur.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {qschema} "
            f"GRANT SELECT, INSERT, UPDATE ON TABLES TO {qrole}"
        )


def grant_app_query_privileges(
    conn: psycopg.Connection,
    *,
    app_role_name: str,
    schema_name: str,
    table_name: str,
) -> None:
    qrole = _quote_ident(app_role_name)
    qschema = _quote_ident(schema_name)
    qtable = _quote_ident(table_name)
    with conn.cursor() as cur:
        cur.execute(f"GRANT USAGE ON SCHEMA {qschema} TO {qrole}")
        cur.execute(f"GRANT SELECT ON TABLE {qschema}.{qtable} TO {qrole}")
        cur.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {qschema} "
            f"GRANT SELECT ON TABLES TO {qrole}"
        )
