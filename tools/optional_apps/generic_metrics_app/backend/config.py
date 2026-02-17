from __future__ import annotations

import os


class AppConfig:
    def __init__(self) -> None:
        self.host = os.environ.get("DATABRICKS_HOST", "")
        self.warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        self.token = os.environ.get("DATABRICKS_TOKEN", "")
        self.client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
        self.client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")

        self.catalog = os.environ.get("APP_TARGET_CATALOG", "main")
        self.schema = os.environ.get("APP_TARGET_SCHEMA", "default")
        self.table = os.environ.get("APP_TARGET_TABLE", "raw_tags")

        self.static_dir = os.environ.get("STATIC_DIR", "./frontend")
        self.port = int(os.environ.get("PORT", "8000"))

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
        if not has_pat and not has_sp:
            raise ValueError(
                "Provide either DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET"
            )


def load_config() -> AppConfig:
    cfg = AppConfig()
    cfg.validate()
    return cfg

