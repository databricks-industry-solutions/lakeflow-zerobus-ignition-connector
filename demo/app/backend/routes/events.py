import time

from fastapi import APIRouter, Query

from ..services import query as query_service
from ..services.query import QueryError
from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/events")


@router.get("/latest")
async def events_latest(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    start = time.monotonic()
    try:
        data = await query_service.execute("eventsLatest", limit=limit)
    except QueryError as exc:
        return _wrap([], start, error=exc.message)
    return _wrap(data, start)
