"""Gate test for AC-19: Fleet snapshot endpoint exists."""
from __future__ import annotations

import inspect

import pytest


class TestAc19:
    def test_ac19_fleet_snapshot_route_exists(self):
        try:
            from backend.routes import time_travel
        except ImportError:
            pytest.fail(
                "GATE NOT PASSED: AC-19 — backend.routes.time_travel module does not exist"
            )
        source = inspect.getsource(time_travel)
        assert "fleet/snapshot" in source or "fleet_snapshot" in source, (
            "GATE FAILED: AC-19 — No fleet/snapshot route found in time_travel module"
        )

    def test_ac19_fleet_snapshot_query_builder(self):
        from backend.services import query as query_service

        assert "fleetSnapshot" in query_service.QUERY_BUILDERS, (
            "GATE NOT PASSED: AC-19 — 'fleetSnapshot' not in QUERY_BUILDERS"
        )
