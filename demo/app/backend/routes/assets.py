import time

from fastapi import APIRouter, HTTPException, Query

from ..services import query as query_service
from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/assets")


@router.get("")
async def list_assets() -> dict:
    start = time.monotonic()
    data = await query_service.execute("assets")
    return _wrap(data, start)


@router.get("/{asset_id}")
async def get_asset(asset_id: str) -> dict:
    start = time.monotonic()
    data = await query_service.execute("assetById", asset_id=asset_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")
    return _wrap(data[0], start)


@router.get("/{asset_id}/tags")
async def get_asset_tags(
    asset_id: str,
    tags: str | None = Query(default=None),
    range: int = Query(default=5, alias="range"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    resolution: str | None = Query(default=None),
) -> dict:
    start = time.monotonic()
    tag_list = tags.split(",") if tags else None
    if from_ and to:
        data = await query_service.execute(
            "assetTagsRange",
            asset_id=asset_id,
            from_ts=from_,
            to_ts=to,
            resolution=resolution,
            tags=tag_list,
        )
    else:
        data = await query_service.execute(
            "assetTags", asset_id=asset_id, tags=tag_list, range_minutes=range
        )
    return _wrap(data, start)
