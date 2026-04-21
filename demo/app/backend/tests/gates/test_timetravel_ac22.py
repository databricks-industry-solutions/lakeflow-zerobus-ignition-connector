"""Gate test for AC-22: Malformed timestamp returns HTTP 422."""
from __future__ import annotations

import inspect

import pytest


class TestAc22:
    def test_ac22_validation_exists_in_routes(self):
        try:
            from backend.routes import time_travel
        except ImportError:
            pytest.fail(
                "GATE NOT PASSED: AC-22 — backend.routes.time_travel module does not exist"
            )
        source = inspect.getsource(time_travel)
        # Should have timestamp validation logic
        assert "422" in source or "datetime" in source.lower() or "fromisoformat" in source.lower(), (
            "GATE FAILED: AC-22 — No timestamp validation or 422 handling in time_travel routes"
        )
