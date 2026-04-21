from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .services.query import QueryService

app = FastAPI(title="Generic Zerobus Metrics App", version="0.1.0")

try:
    config = load_config()
    query_service = QueryService(
        warehouse_id=config.warehouse_id,
        catalog=config.catalog,
        schema=config.schema,
        table=config.table,
    )
except Exception as exc:
    config = None
    query_service = None
    startup_error = str(exc)
else:
    startup_error = ""


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok" if query_service else "degraded",
        "configured": bool(query_service),
        "error": startup_error,
    }


def _require_service() -> QueryService:
    if not query_service:
        raise HTTPException(status_code=503, detail=f"App not configured: {startup_error}")
    return query_service


@app.get("/api/metrics/throughput")
def metrics_throughput(minutes: int = Query(default=15, ge=1, le=1440)) -> dict:
    svc = _require_service()
    return {"data": svc.throughput(minutes)}


@app.get("/api/metrics/latency")
def metrics_latency(minutes: int = Query(default=15, ge=1, le=1440)) -> dict:
    svc = _require_service()
    return {"data": svc.latency(minutes)}


@app.get("/api/metrics/compression")
def metrics_compression(minutes: int = Query(default=15, ge=1, le=1440)) -> dict:
    svc = _require_service()
    return {"data": svc.compression(minutes)}


static_dir = Path(config.static_dir if config else "./frontend")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index() -> FileResponse:
    index_path = static_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html not found")
    return FileResponse(index_path)

