"""Time Travel and Historical Replay routes.

Provides:
- GET /api/fleet/snapshot       — Point-in-time fleet health (scored_at history)
- GET /api/assets/{id}/tags/export — CSV export for a time range
- GET /api/assets/{id}/forensics   — Raw events ±window around an event timestamp
"""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..services import query as query_service
from ..services.query import QueryError
from .helpers import wrap as _wrap

router = APIRouter()


def _parse_iso(value: str, param_name: str) -> datetime:
    """Parse an ISO 8601 timestamp string; raise HTTP 422 on failure."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid ISO 8601 timestamp for '{param_name}': {value!r}",
        )


@router.get("/api/fleet/snapshot")
async def fleet_snapshot(
    timestamp: str = Query(..., description="ISO 8601 point-in-time timestamp"),
) -> dict:
    """Return fleet health scores at or before the given timestamp (SCD-style history)."""
    start = time.monotonic()
    _parse_iso(timestamp, "timestamp")
    data = await query_service.execute("fleetSnapshot", timestamp=timestamp)
    result = _wrap(data, start)
    result["meta"]["snapshot_timestamp"] = timestamp
    return result


@router.get("/api/assets/{asset_id}/tags/export")
async def export_asset_tags(
    asset_id: str,
    from_: str = Query(..., alias="from", description="ISO 8601 start timestamp"),
    to: str = Query(..., description="ISO 8601 end timestamp"),
    format: str = Query(default="csv"),
) -> StreamingResponse:
    """Stream tag data as CSV for the given asset and time range."""
    _parse_iso(from_, "from")
    _parse_iso(to, "to")

    data = await query_service.execute(
        "assetTagsExport", asset_id=asset_id, from_ts=from_, to_ts=to
    )

    if len(data) > 100_000:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Export would return {len(data):,} rows (limit: 100,000). "
                "Please narrow your time range."
            ),
        )

    def _generate():
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["event_timestamp", "tag_name", "tag_value", "quality", "sdt_compressed"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        yield buf.getvalue()

    safe_from = from_.replace(":", "-").replace("+", "")
    safe_to = to.replace(":", "-").replace("+", "")
    filename = f"{asset_id}_{safe_from}_{safe_to}.csv"

    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/assets/{asset_id}/forensics")
async def asset_forensics(
    asset_id: str,
    event_time: str = Query(..., description="ISO 8601 event timestamp"),
    window_minutes: int = Query(default=30, ge=1, le=1440),
) -> dict:
    """Return raw tag events for ±window_minutes around the given event timestamp."""
    start = time.monotonic()
    _parse_iso(event_time, "event_time")
    data = await query_service.execute(
        "assetForensics",
        asset_id=asset_id,
        event_time=event_time,
        window_minutes=window_minutes,
    )
    result = _wrap(data, start)
    result["meta"]["event_time"] = event_time
    return result
