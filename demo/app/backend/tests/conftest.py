"""Pytest configuration and fixtures for demo app backend tests."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require Databricks (workspace, warehouse, ot_demo.ot.raw_tags with data). "
        "Skip when DATABRICKS_WAREHOUSE_ID is not set; auth can be env or ~/.databrickscfg profile.",
    )


def _databricks_configured() -> bool:
    """True if warehouse is set; auth may come from env or ~/.databrickscfg profile."""
    return bool(os.environ.get("DATABRICKS_WAREHOUSE_ID", "").strip())


@pytest.fixture(scope="session")
def databricks_env_available() -> bool:
    return _databricks_configured()


@pytest.fixture
def catalog() -> str:
    return os.environ.get("APP_TARGET_CATALOG", os.environ.get("DATABRICKS_CATALOG", "ot_demo"))


@pytest.fixture
def schema() -> str:
    return os.environ.get("APP_TARGET_SCHEMA", os.environ.get("DATABRICKS_SCHEMA", "ot"))
