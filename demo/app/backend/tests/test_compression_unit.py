"""Unit tests for compression layer-building (no Databricks)."""

from __future__ import annotations

import pytest

from backend.routes.compression import BYTES_PER_ROW_RAW, build_compression_layers


def test_build_compression_layers_four_entries():
    """build_compression_layers returns exactly four layers with expected names."""
    comparison_rows = [
        {
            "total_raw": 1000,
            "total_after_sdt": 800,
            "total_bytes": 80_000,
        }
    ]
    storage_rows = [{"total_bytes": 20_000}]

    layers = build_compression_layers(comparison_rows, storage_rows)

    assert len(layers) == 4
    assert [l["layer_name"] for l in layers] == ["raw", "after_sdt", "after_delta", "combined"]


def test_build_compression_layers_math():
    """Layer sizes and ratios match raw = total_raw * 150, after_sdt/delta from queries."""
    total_raw = 1000
    total_after_sdt = 800
    total_bytes_estimate = 80_000
    delta_total_bytes = 20_000

    comparison_rows = [
        {
            "total_raw": total_raw,
            "total_after_sdt": total_after_sdt,
            "total_bytes": total_bytes_estimate,
        }
    ]
    storage_rows = [{"total_bytes": delta_total_bytes}]

    layers = build_compression_layers(comparison_rows, storage_rows)

    raw_layer = next(l for l in layers if l["layer_name"] == "raw")
    assert raw_layer["event_count"] == total_raw
    assert raw_layer["size_bytes"] == total_raw * BYTES_PER_ROW_RAW  # 150_000
    assert raw_layer["ratio_vs_raw"] == 1.0

    after_sdt_layer = next(l for l in layers if l["layer_name"] == "after_sdt")
    assert after_sdt_layer["event_count"] == total_after_sdt
    assert after_sdt_layer["size_bytes"] == total_bytes_estimate
    assert after_sdt_layer["ratio_vs_raw"] == pytest.approx(150_000 / 80_000)

    after_delta_layer = next(l for l in layers if l["layer_name"] == "after_delta")
    assert after_delta_layer["size_bytes"] == delta_total_bytes
    assert after_delta_layer["ratio_vs_raw"] == pytest.approx(150_000 / 20_000)

    combined = next(l for l in layers if l["layer_name"] == "combined")
    assert combined["size_bytes"] == delta_total_bytes
    assert combined["ratio_vs_raw"] == after_delta_layer["ratio_vs_raw"]


def test_build_compression_layers_empty_comparison():
    """When comparison is empty, layers have zeros; after_delta falls back to after_sdt."""
    layers = build_compression_layers([], [])

    assert len(layers) == 4
    raw = next(l for l in layers if l["layer_name"] == "raw")
    assert raw["event_count"] == 0
    assert raw["size_bytes"] == 0

    after_sdt = next(l for l in layers if l["layer_name"] == "after_sdt")
    assert after_sdt["size_bytes"] == 0

    after_delta = next(l for l in layers if l["layer_name"] == "after_delta")
    assert after_delta["size_bytes"] == 0


def test_build_compression_layers_empty_storage_uses_after_sdt():
    """When storage_rows is empty, after_delta size equals after_sdt (fallback)."""
    comparison_rows = [{"total_raw": 100, "total_after_sdt": 100, "total_bytes": 10_000}]
    storage_rows = []

    layers = build_compression_layers(comparison_rows, storage_rows)

    after_sdt = next(l for l in layers if l["layer_name"] == "after_sdt")
    after_delta = next(l for l in layers if l["layer_name"] == "after_delta")
    assert after_delta["size_bytes"] == after_sdt["size_bytes"] == 10_000


def test_build_compression_layers_alternate_column_names():
    """Handles TOTAL_RAW, TOTAL_AFTER_SDT, TOTAL_BYTES (uppercase) from API."""
    comparison_rows = [
        {
            "TOTAL_RAW": 500,
            "TOTAL_AFTER_SDT": 400,
            "TOTAL_BYTES": 40_000,
        }
    ]
    storage_rows = [{"TOTAL_BYTES": 12_000}]

    layers = build_compression_layers(comparison_rows, storage_rows)

    raw = next(l for l in layers if l["layer_name"] == "raw")
    assert raw["size_bytes"] == 500 * BYTES_PER_ROW_RAW

    after_delta = next(l for l in layers if l["layer_name"] == "after_delta")
    assert after_delta["size_bytes"] == 12_000
