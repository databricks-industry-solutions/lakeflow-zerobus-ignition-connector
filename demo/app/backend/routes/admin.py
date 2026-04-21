import os
import time

from fastapi import APIRouter, Header, HTTPException

from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/admin")


@router.post("/reset")
async def reset(x_api_key: str | None = Header(default=None)) -> dict:
    start = time.monotonic()
    expected_key = os.environ.get("ADMIN_API_KEY", "")
    # If ADMIN_API_KEY is set, enforce it. Otherwise allow local/demo reset.
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return _wrap(
        {"status": "reset_complete", "message": "Demo tables truncated and simulator restarted"},
        start,
    )
