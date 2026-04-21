from __future__ import annotations

import os


class AppConfig:
    def __init__(self) -> None:
        self.host = os.environ.get("DATABRICKS_HOST", "")
        self.warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        self.token = os.environ.get("DATABRICKS_TOKEN", "")
        self.client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
        self.client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
        self.auth_type = os.environ.get("DATABRICKS_AUTH_TYPE", "")
        self.config_profile = os.environ.get("DATABRICKS_CONFIG_PROFILE", "")

        self.catalog = os.environ.get("APP_TARGET_CATALOG", "main")
        self.schema = os.environ.get("APP_TARGET_SCHEMA", "default")
        self.table = os.environ.get("APP_TARGET_TABLE", "raw_tags")

        self.static_dir = os.environ.get("STATIC_DIR", "./frontend")
        self.port = int(os.environ.get("PORT", "8000"))

        # Optional dual-sink (Lakebase/PostgreSQL) settings.
        # If PG_DSN is unset, dual-sink metrics routes remain disabled.
        self.pg_dsn = os.environ.get("PG_DSN", "")
        self.pg_table = os.environ.get("PG_TABLE", "raw_tags")

    def validate(self) -> None:
        missing = []
        if not self.host:
            missing.append("DATABRICKS_HOST")
        if not self.warehouse_id:
            missing.append("DATABRICKS_WAREHOUSE_ID")
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

        has_pat = bool(self.token)
        has_sp = bool(self.client_id and self.client_secret)
        has_profile = bool(self.config_profile) or self.auth_type == "databricks-cli"
        if not has_pat and not has_sp and not has_profile:
            raise ValueError(
                "Provide either DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET "
                "or DATABRICKS_CONFIG_PROFILE/DATABRICKS_AUTH_TYPE=databricks-cli"
            )


def load_config() -> AppConfig:
    cfg = AppConfig()
    cfg.validate()
    return cfg

