"""Gate test for AC-7: Fleet snapshot query filters by scored_at for point-in-time history."""
from __future__ import annotations

import pytest

from backend.services import query as query_service


class TestAc7:
    def test_ac7_fleet_snapshot_queries_by_scored_at(self):
        try:
            sql, params = query_service.build_query(
                "fleetSnapshot",
                timestamp="2026-03-24T12:00:00Z",
            )
        except (ValueError, TypeError) as exc:
            pytest.fail(
                f"GATE NOT PASSED: AC-7 — 'fleetSnapshot' query builder not found or wrong signature: {exc}"
            )
        assert "scored_at" in sql.lower(), (
            f"GATE FAILED: AC-7 — Expected scored_at filter in fleet snapshot SQL, got:\n{sql[:500]}"
        )
        assert "ROW_NUMBER" in sql or "QUALIFY" in sql, (
            f"GATE FAILED: AC-7 — Expected QUALIFY/ROW_NUMBER for latest-per-asset, got:\n{sql[:500]}"
        )
