"""Gate test for AC-18: raw resolution capped at 10K rows."""
from __future__ import annotations

import re

import pytest

from backend.services import query as query_service


class TestAc18:
    def test_ac18_raw_resolution_has_row_cap(self):
        try:
            sql, params = query_service.build_query(
                "assetTagsRange",
                asset_id="bess01",
                from_ts="2026-03-24T10:00:00Z",
                to_ts="2026-03-24T12:00:00Z",
                resolution="raw",
            )
        except (ValueError, TypeError) as exc:
            pytest.fail(
                f"GATE NOT PASSED: AC-18 — assetTagsRange with resolution=raw failed: {exc}"
            )
        # Should contain a LIMIT clause for raw mode
        assert re.search(r"LIMIT\s+\d", sql, re.IGNORECASE), (
            f"GATE FAILED: AC-18 — Expected LIMIT clause for raw resolution, got:\n{sql[:500]}"
        )
