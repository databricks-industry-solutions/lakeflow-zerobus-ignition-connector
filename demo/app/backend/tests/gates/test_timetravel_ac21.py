"""Gate test for AC-21: Forensics endpoint exists."""
from __future__ import annotations

import inspect

import pytest


class TestAc21:
    def test_ac21_forensics_route_exists(self):
        try:
            from backend.routes import time_travel
        except ImportError:
            pytest.fail(
                "GATE NOT PASSED: AC-21 — backend.routes.time_travel module does not exist"
            )
        source = inspect.getsource(time_travel)
        assert "forensics" in source.lower(), (
            "GATE FAILED: AC-21 — No forensics route found in time_travel module"
        )

    def test_ac21_forensics_query_builder(self):
        from backend.services import query as query_service

        assert "assetForensics" in query_service.QUERY_BUILDERS, (
            "GATE NOT PASSED: AC-21 — 'assetForensics' not in QUERY_BUILDERS"
        )
