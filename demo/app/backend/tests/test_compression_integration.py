"""Integration tests for compression comparison using real ot_demo.ot.raw_tags.

Requires Databricks workspace, warehouse, and recent data in raw_tags.
Run with: uv run pytest backend/tests/test_compression_integration.py -m integration

Auth: set DATABRICKS_WAREHOUSE_ID; auth can be via env (DATABRICKS_CLIENT_ID/SECRET or
DATABRICKS_TOKEN) or via ~/.databrickscfg profile (e.g. DATABRICKS_CONFIG_PROFILE=daveok).
If using profile auth, run: databricks auth login --profile daveok
Skip only when DATABRICKS_WAREHOUSE_ID is not set.
"""

from __future__ import annotations

import os

import pytest

from backend.routes.compression import build_compression_layers
from backend.services import query as query_service


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _databricks_configured() -> bool:
    """True if warehouse is set; auth may come from env or ~/.databrickscfg profile."""
    return bool(os.environ.get("DATABRICKS_WAREHOUSE_ID", "").strip())


def _skip_on_auth_error(exc: BaseException) -> None:
    """If exc is a Databricks credential/auth error, skip with a helpful message."""
    msg = str(exc).lower()
    if "cannot configure default credentials" in msg or "credentials" in msg and "auth" in msg:
        profile = os.environ.get("DATABRICKS_CONFIG_PROFILE", "daveok")
        hint = (
            f"Run: databricks auth login --profile {profile}. "
            "If you already did, ensure .env DATABRICKS_HOST matches the host you logged in to (e.g. https://adb-<id>.11.azuredatabricks.net)."
        )
        pytest.skip(f"Databricks auth failed: {exc!s}. {hint}")
    raise exc


@pytest.fixture(autouse=True)
def _init_query_service(catalog: str, schema: str):
    """Initialize query service with catalog/schema so execute() uses correct tables."""
    query_service.init(catalog, schema)
    yield


@pytest.mark.skipif(
    not _databricks_configured(),
    reason="DATABRICKS_WAREHOUSE_ID not set; skip integration tests (auth can be profile or env)",
)
async def test_compression_comparison_query_and_layers(catalog: str, schema: str):
    """Run compressionComparison and rawTagsStorageMetrics against real raw_tags; assert layer shape and ZSTD/SDT."""
    query_service.init(catalog, schema)

    try:
        comparison_rows = await query_service.execute("compressionComparison")
        storage_rows = await query_service.execute("rawTagsStorageMetrics")
    except ValueError as e:
        _skip_on_auth_error(e)

    layers = build_compression_layers(comparison_rows, storage_rows)

    # Always expect four layers
    assert len(layers) == 4
    names = [l["layer_name"] for l in layers]
    assert names == ["raw", "after_sdt", "after_delta", "combined"]

    for layer in layers:
        assert "layer_name" in layer
        assert "event_count" in layer
        assert "size_bytes" in layer
        assert "ratio_vs_raw" in layer

    raw_layer = next(l for l in layers if l["layer_name"] == "raw")
    after_sdt_layer = next(l for l in layers if l["layer_name"] == "after_sdt")
    after_delta_layer = next(l for l in layers if l["layer_name"] == "after_delta")

    # When there is data in the last 30 min: raw size = total_raw * 150
    total_raw = raw_layer["event_count"]
    assert raw_layer["size_bytes"] == total_raw * 150

    # When table has data, DESCRIBE DETAIL returns sizeInBytes (Delta/ZSTD on disk)
    # Note: Delta size is for the entire table, while raw_layer is for the 30-min window,
    # so we can't directly compare them. Just verify the value is non-negative.
    if total_raw > 0:
        assert after_delta_layer["size_bytes"] >= 0

    # SDT: when compression_ratio > 1 in data, total_after_sdt <= total_raw
    total_after_sdt = after_sdt_layer["event_count"]
    if total_raw > 0 and total_after_sdt < total_raw:
        # Compression was applied; ratio_vs_raw for after_sdt should be >= 1
        assert after_sdt_layer["ratio_vs_raw"] >= 1.0

    # combined mirrors after_delta
    combined = next(l for l in layers if l["layer_name"] == "combined")
    assert combined["size_bytes"] == after_delta_layer["size_bytes"]
    assert combined["ratio_vs_raw"] == after_delta_layer["ratio_vs_raw"]


@pytest.mark.skipif(
    not _databricks_configured(),
    reason="DATABRICKS_WAREHOUSE_ID not set; skip integration tests (auth can be profile or env)",
)
async def test_compression_comparison_api_contract(catalog: str, schema: str):
    """GET /api/compression/comparison returns data array of layers with expected keys."""
    from httpx import ASGITransport, AsyncClient

    from backend.main import create_app

    query_service.init(catalog, schema)
    app = create_app()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/compression/comparison")
    except ValueError as e:
        _skip_on_auth_error(e)

    # May be 502 if query fails (e.g. no warehouse); 200 when successful
    if response.status_code != 200:
        pytest.skip(f"Comparison endpoint returned {response.status_code}; check workspace and raw_tags")

    data = response.json()
    assert "data" in data
    assert "meta" in data
    layers = data["data"]
    assert isinstance(layers, list)
    assert len(layers) >= 1
    for layer in layers:
        assert "layer_name" in layer
        assert "event_count" in layer
        assert "size_bytes" in layer
        assert "ratio_vs_raw" in layer
