import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import query as query_service
from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/compression")


class SdtConfigUpdate(BaseModel):
    tag_pattern: str
    comp_dev: float | None = None
    comp_dev_percent: float | None = Field(default=None, ge=0.1, le=5.0)
    comp_max_seconds: int | None = Field(default=None, ge=60, le=3600)
    comp_min_seconds: int | None = None


# Bytes per row estimate for "raw" (uncompressed equivalent) layer in the waterfall.
BYTES_PER_ROW_RAW = 150


def _get_int(row: dict, *keys: str, default: int = 0) -> int:
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return default


def build_compression_layers(
    comparison_rows: list[dict],
    storage_rows: list[dict],
    total_count_rows: list[dict] | None = None,
) -> list[dict]:
    """Build the four compression layers from comparison and storage query results.

    Used by GET /comparison and by unit tests with mocked rows.
    """
    total_raw = 0
    total_after_sdt = 0
    total_bytes_estimate = 0
    if comparison_rows:
        row = comparison_rows[0]
        total_raw = _get_int(row, "total_raw", "TOTAL_RAW")
        total_after_sdt = _get_int(row, "total_after_sdt", "TOTAL_AFTER_SDT")
        total_bytes_estimate = _get_int(row, "total_bytes", "TOTAL_BYTES")

    delta_total_bytes = None
    if storage_rows:
        first = storage_rows[0]
        # DESCRIBE DETAIL returns sizeInBytes; fall back to total_bytes for compat
        delta_total_bytes = (
            first.get("sizeInBytes")
            or first.get("SIZEINBYTES")
            or first.get("total_bytes")
            or first.get("TOTAL_BYTES")
        )
        if delta_total_bytes is not None:
            delta_total_bytes = int(delta_total_bytes)

    # Scale Delta size to the same time window as the raw/SDT estimates.
    # DESCRIBE DETAIL gives the whole-table size; we need the fraction
    # that corresponds to the 30-min window rows.
    total_table_rows = 0
    if total_count_rows:
        total_table_rows = _get_int(total_count_rows[0], "total_rows", "TOTAL_ROWS")

    raw_size = total_raw * BYTES_PER_ROW_RAW
    after_sdt_size = total_after_sdt * BYTES_PER_ROW_RAW
    if delta_total_bytes and total_table_rows > 0 and total_after_sdt > 0:
        # bytes-per-row in Delta ZSTD, scaled to the window row count
        delta_size = int(delta_total_bytes * (total_after_sdt / total_table_rows))
    elif delta_total_bytes is not None and delta_total_bytes > 0:
        delta_size = delta_total_bytes
    else:
        delta_size = after_sdt_size

    def safe_ratio(num: float, denom: float) -> float:
        if denom is None or denom <= 0:
            return 1.0
        return num / denom

    return [
        {
            "layer_name": "raw",
            "event_count": total_raw,
            "size_bytes": raw_size,
            "ratio_vs_raw": 1.0,
        },
        {
            "layer_name": "after_sdt",
            "event_count": total_after_sdt,
            "size_bytes": after_sdt_size,
            "ratio_vs_raw": safe_ratio(raw_size, after_sdt_size),
        },
        {
            "layer_name": "after_delta",
            "event_count": total_after_sdt,
            "size_bytes": delta_size,
            "ratio_vs_raw": safe_ratio(raw_size, delta_size),
        },
        {
            "layer_name": "combined",
            "event_count": total_after_sdt,
            "size_bytes": delta_size,
            "ratio_vs_raw": safe_ratio(raw_size, delta_size),
        },
    ]


@router.get("/comparison")
async def compression_comparison() -> dict:
    start = time.monotonic()
    comparison_rows = await query_service.execute("compressionComparison")
    storage_rows = await query_service.execute("rawTagsStorageMetrics")
    total_count_rows = await query_service.execute("rawTagsTotalCount")
    layers = build_compression_layers(comparison_rows, storage_rows, total_count_rows)
    return _wrap(layers, start)


@router.get("/sdt-config")
async def get_sdt_config() -> dict:
    start = time.monotonic()
    data = await query_service.execute("sdtConfig")
    return _wrap(data, start)


@router.put("/sdt-config")
async def update_sdt_config(body: SdtConfigUpdate) -> dict:
    start = time.monotonic()
    await query_service.execute(
        "sdtConfigUpdate",
        tag_pattern=body.tag_pattern,
        comp_dev=body.comp_dev,
        comp_dev_percent=body.comp_dev_percent,
        comp_max_seconds=body.comp_max_seconds or 600,
        comp_min_seconds=body.comp_min_seconds or 0,
    )
    data = await query_service.execute("sdtConfig")
    return _wrap(data, start)
