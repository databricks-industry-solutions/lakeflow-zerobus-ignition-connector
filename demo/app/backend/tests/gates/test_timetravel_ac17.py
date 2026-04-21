"""Gate test for AC-17: assetTags accepts from/to ISO params."""
from __future__ import annotations

import pytest

from backend.services import query as query_service


class TestAc17:
    def test_ac17_asset_tags_range_query_builder_exists(self):
        assert "assetTagsRange" in query_service.QUERY_BUILDERS, (
            "GATE NOT PASSED: AC-17 — 'assetTagsRange' not registered in QUERY_BUILDERS"
        )

    def test_ac17_asset_tags_range_accepts_from_to(self):
        try:
            sql, params = query_service.build_query(
                "assetTagsRange",
                asset_id="bess01",
                from_ts="2026-03-24T10:00:00Z",
                to_ts="2026-03-24T12:00:00Z",
            )
        except (ValueError, TypeError) as exc:
            pytest.fail(
                f"GATE NOT PASSED: AC-17 — assetTagsRange query builder failed: {exc}"
            )
        assert sql, "GATE FAILED: AC-17 — assetTagsRange returned empty SQL"
        assert len(params) >= 2, (
            f"GATE FAILED: AC-17 — Expected at least 2 params (from, to), got {len(params)}"
        )
