"""Gate test for AC-4: 3-day range produces 15-min downsampled SQL."""
from __future__ import annotations

import re

import pytest

from backend.services import query as query_service


class TestAc4:
    def test_ac4_three_day_range_uses_15min_bucketing(self):
        # The query builder 'assetTagsRange' should exist and produce
        # time-bucketed SQL for ranges > 24h
        try:
            sql, params = query_service.build_query(
                "assetTagsRange",
                asset_id="bess01",
                from_ts="2026-03-20T00:00:00Z",
                to_ts="2026-03-23T00:00:00Z",
                resolution=None,  # auto-select
            )
        except (ValueError, TypeError) as exc:
            pytest.fail(
                f"GATE NOT PASSED: AC-4 — 'assetTagsRange' query builder not found or wrong signature: {exc}"
            )
        # SQL should contain time bucketing logic (DATE_TRUNC or FLOOR/UNIX_TIMESTAMP)
        has_bucketing = bool(
            re.search(r"DATE_TRUNC|FLOOR.*UNIX_TIMESTAMP|TIMESTAMP_SECONDS", sql, re.IGNORECASE)
        )
        assert has_bucketing, (
            f"GATE FAILED: AC-4 — Expected time-bucketing SQL for 3-day range, got:\n{sql[:500]}"
        )
        # Should be 15-minute resolution for 1d < range <= 7d
        has_15min = bool(re.search(r"15|900", sql))
        assert has_15min, (
            f"GATE FAILED: AC-4 — Expected 15-minute bucketing for 3-day range, got:\n{sql[:500]}"
        )
