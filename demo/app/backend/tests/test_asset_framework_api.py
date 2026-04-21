"""API tests for asset framework hierarchy tag explorer endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.services import query as query_service


@pytest.mark.asyncio
async def test_get_hierarchy_asset_tags_calls_query_with_params(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_execute(name: str, **kwargs: object):
        calls.append((name, kwargs))
        if name == "hierarchyAssetTags":
            return [
                {
                    "asset_id": "tomago_bess01",
                    "tag_name": "telemetry/soc_pct",
                    "is_mapped": True,
                }
            ]
        return []

    monkeypatch.setattr(query_service, "execute", fake_execute)
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/asset-framework/hierarchy/tomago_bess01/tags"
            "?minutes=15&include_unmapped=false"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["tag_name"] == "telemetry/soc_pct"
    assert calls == [
        (
            "hierarchyAssetTags",
            {
                "asset_id": "tomago_bess01",
                "minutes": 15,
                "include_unmapped": False,
            },
        )
    ]


@pytest.mark.asyncio
async def test_get_hierarchy_tag_summary_calls_query(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_execute(name: str, **kwargs: object):
        calls.append((name, kwargs))
        if name == "hierarchyAssetTagSummary":
            return [
                {
                    "asset_id": "tomago_bess01",
                    "mapped_tag_count": 20,
                    "live_tag_count": 24,
                    "mapped_live_tag_count": 20,
                    "unmapped_tag_count": 4,
                }
            ]
        return []

    monkeypatch.setattr(query_service, "execute", fake_execute)
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/asset-framework/hierarchy/tag-summary?minutes=45"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["unmapped_tag_count"] == 4
    assert calls == [("hierarchyAssetTagSummary", {"minutes": 45})]
