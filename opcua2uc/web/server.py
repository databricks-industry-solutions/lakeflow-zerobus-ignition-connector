from __future__ import annotations

import json
from pathlib import Path

from aiohttp import web

from opcua2uc.config import AppConfig, load_config, save_config
from opcua2uc.core.bridge import Bridge


class WebServer:
    """
    Embedded web server for the connector.

    - Serves a bundled UI (static) on /
    - Exposes a small REST API under /api/*
    """

    def __init__(self, bridge: Bridge, config_path: str, port: int = 8080) -> None:
        self.bridge = bridge
        self.port = port
        self.config_path = config_path

        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self) -> None:
        static_dir = Path(__file__).parent / "static"
        vendor_dir = static_dir / "vendor"

        self.app.router.add_get("/", self._serve_index)
        self.app.router.add_static("/static", static_dir)
        # Vendor is nested under static as well; the explicit route helps readability.
        self.app.router.add_static("/vendor", vendor_dir)

        self.app.router.add_get("/api/status", self._get_status)
        self.app.router.add_get("/api/sources", self._get_sources)
        self.app.router.add_post("/api/sources", self._add_source)
        self.app.router.add_delete("/api/sources/{name}", self._delete_source)
        self.app.router.add_post("/api/sources/{name}/test", self._test_source)
        self.app.router.add_get("/api/config", self._get_config)
        self.app.router.add_post("/api/config", self._set_config)

        self.app.router.add_get("/health/live", self._live)
        self.app.router.add_get("/health/ready", self._ready)

    async def _serve_index(self, request: web.Request) -> web.StreamResponse:
        index_path = Path(__file__).parent / "static" / "index.html"
        return web.FileResponse(index_path)

    async def _get_status(self, request: web.Request) -> web.StreamResponse:
        return web.json_response(self.bridge.get_detailed_status())

    async def _get_sources(self, request: web.Request) -> web.StreamResponse:
        return web.json_response(self.bridge.get_sources())

    async def _add_source(self, request: web.Request) -> web.StreamResponse:
        try:
            payload = await request.json()
        except Exception:
            body = await request.text()
            return web.json_response({"error": "Invalid JSON", "body": body}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"error": "Source must be a JSON object"}, status=400)

        name = (payload.get("name") or "").strip()
        endpoint = (payload.get("endpoint") or "").strip()
        if not name:
            return web.json_response({"error": "Missing field: name"}, status=400)
        if not endpoint:
            return web.json_response({"error": "Missing field: endpoint"}, status=400)

        cfg = load_config(self.config_path)
        if any((s.get("name") or "").strip() == name for s in cfg.sources):
            return web.json_response({"error": f"Source already exists: {name}"}, status=409)

        cfg.sources.append({"name": name, "endpoint": endpoint})
        save_config(self.config_path, cfg)
        self.bridge.set_config(cfg)
        return web.json_response({"ok": True, "source": {"name": name, "endpoint": endpoint}})

    async def _delete_source(self, request: web.Request) -> web.StreamResponse:
        name = (request.match_info.get("name") or "").strip()
        if not name:
            return web.json_response({"error": "Missing source name"}, status=400)

        cfg = load_config(self.config_path)
        before = len(cfg.sources)
        cfg.sources = [s for s in cfg.sources if (s.get("name") or "").strip() != name]
        if len(cfg.sources) == before:
            return web.json_response({"error": f"Source not found: {name}"}, status=404)

        save_config(self.config_path, cfg)
        self.bridge.set_config(cfg)
        return web.json_response({"ok": True})

    async def _test_source(self, request: web.Request) -> web.StreamResponse:
        # Placeholder: later perform real OPC UA connection test.
        name = (request.match_info.get("name") or "").strip()
        if not name:
            return web.json_response({"error": "Missing source name"}, status=400)

        cfg = load_config(self.config_path)
        match = next((s for s in cfg.sources if (s.get("name") or "").strip() == name), None)
        if not match:
            return web.json_response({"error": f"Source not found: {name}"}, status=404)

        return web.json_response(
            {
                "ok": True,
                "name": name,
                "endpoint": match.get("endpoint"),
                "note": "Simulated test (OPC UA client not implemented yet).",
            }
        )

    async def _get_config(self, request: web.Request) -> web.StreamResponse:
        cfg = load_config(self.config_path)
        return web.json_response(cfg.to_dict())

    async def _set_config(self, request: web.Request) -> web.StreamResponse:
        try:
            payload = await request.json()
        except Exception:
            body = await request.text()
            return web.json_response({"error": "Invalid JSON", "body": body}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"error": "Config must be a JSON object"}, status=400)

        try:
            cfg = AppConfig.from_dict(payload)
            save_config(self.config_path, cfg)
            self.bridge.set_config(cfg)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

        return web.json_response({"ok": True})

    async def _live(self, request: web.Request) -> web.StreamResponse:
        return web.json_response({"status": "live"})

    async def _ready(self, request: web.Request) -> web.StreamResponse:
        # For now: ready if the process is up. Later: validate OPC UA + Databricks connectivity.
        return web.json_response({"status": "ready"})

    async def start(self) -> None:
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()


