"""Gate test for AC-20: CSV export endpoint exists with correct headers."""
from __future__ import annotations

import inspect

import pytest


class TestAc20:
    def test_ac20_export_route_exists(self):
        try:
            from backend.routes import time_travel
        except ImportError:
            pytest.fail(
                "GATE NOT PASSED: AC-20 — backend.routes.time_travel module does not exist"
            )
        source = inspect.getsource(time_travel)
        assert "export" in source.lower(), (
            "GATE FAILED: AC-20 — No export route found in time_travel module"
        )
        assert "text/csv" in source or "Content-Disposition" in source, (
            "GATE FAILED: AC-20 — Export route missing CSV content type or disposition header"
        )
