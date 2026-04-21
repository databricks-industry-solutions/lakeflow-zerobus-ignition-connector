"""Shared route helpers."""

import time
from datetime import datetime, timezone


def wrap(
    data: object,
    start: float,
    source: str | None = None,
    error: str | None = None,
) -> dict:
    """Wrap a response payload with standard metadata."""
    meta: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_time_ms": round((time.monotonic() - start) * 1000),
    }
    if source:
        meta["source"] = source
    if error:
        meta["error"] = error
    return {"data": data, "meta": meta}
