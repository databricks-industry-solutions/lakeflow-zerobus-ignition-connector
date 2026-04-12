from __future__ import annotations

import os


class AppConfig:
    """Application configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.host: str = os.environ.get("DATABRICKS_HOST", "")
        self.http_path: str = os.environ.get("DATABRICKS_HTTP_PATH", "")
        self.token: str = os.environ.get("DATABRICKS_TOKEN", "")
        self.client_id: str = os.environ.get("DATABRICKS_CLIENT_ID", "")
        self.client_secret: str = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
        self.warehouse_id: str = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        self.catalog: str = os.environ.get("APP_TARGET_CATALOG", os.environ.get("DATABRICKS_CATALOG", "ot_demo"))
        self.schema: str = os.environ.get("APP_TARGET_SCHEMA", os.environ.get("DATABRICKS_SCHEMA", "ot"))
        self.port: int = int(os.environ.get("PORT", "8000"))
        self.cors_origins: list[str] = os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173"
        ).split(",")
        self.admin_api_key: str = os.environ.get("ADMIN_API_KEY", "")

    def validate(self) -> None:
        """Raise ValueError if required config is missing."""
        missing: list[str] = []
        if not self.host:
            missing.append("DATABRICKS_HOST")
        if not self.http_path:
            missing.append("DATABRICKS_HTTP_PATH")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        has_sp = bool(self.client_id and self.client_secret)
        has_token = bool(self.token)
        if not has_sp and not has_token:
            raise ValueError(
                "Missing authentication: provide either "
                "DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET "
                "(service principal) or DATABRICKS_TOKEN (PAT)"
            )


def load_config() -> AppConfig:
    config = AppConfig()
    config.validate()
    return config
