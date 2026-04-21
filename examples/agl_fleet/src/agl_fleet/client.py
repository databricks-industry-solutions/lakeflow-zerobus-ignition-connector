"""HTTP client for posting tag events to Ignition Gateway's Zerobus ingest endpoint."""

from __future__ import annotations

import os
import re

import httpx

from .generators import TagEvent


def _workspace_id_from_url(url: str) -> str | None:
    """Extract workspace ID from workspace URL (e.g. adb-7405607216190670.10.azuredatabricks.net)."""
    m = re.search(r"adb-(\d+)", url)
    return m.group(1) if m else None


def _workspace_id_from_zerobus_endpoint(endpoint: str) -> str | None:
    """Extract workspace ID from Zerobus endpoint (e.g. 7405607216190670.zerobus.eastus2.azuredatabricks.net)."""
    part = endpoint.strip().split(".")[0]
    return part if part.isdigit() else None


def validate_workspace_and_endpoint(workspace_url: str, zerobus_endpoint: str) -> None:
    """Raise ValueError if workspace URL and Zerobus endpoint do not refer to the same workspace."""
    wid_url = _workspace_id_from_url(workspace_url)
    wid_ep = _workspace_id_from_zerobus_endpoint(zerobus_endpoint)
    if not wid_url or not wid_ep:
        return  # skip if we can't parse
    if wid_url != wid_ep:
        raise ValueError(
            f"Workspace URL and Zerobus endpoint must be for the same workspace. "
            f"Workspace URL has ID {wid_url!r}, endpoint has {wid_ep!r}. "
            f"Fix [agl-demo] host in ~/.databrickscfg or ZEROBUS_ENDPOINT so they match."
        )


def _build_payload(events: list[TagEvent]) -> list[dict]:
    return [
        {
            "tagPath": e.tag_path,
            "value": e.value,
            "qualityCode": e.quality_code,
            "timestamp": e.timestamp_ms,
            "dataType": e.data_type,
        }
        for e in events
    ]


class GatewayClient:
    """Posts tag events to the Ignition Gateway /system/zerobus/ingest/batch endpoint."""

    def __init__(self, gateway_url: str, api_key: str | None = None, timeout: float = 10.0):
        self.base_url = gateway_url.rstrip("/")
        self.url = f"{self.base_url}/system/zerobus/ingest/batch"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(headers=headers, timeout=timeout)

    def send_batch(self, events: list[TagEvent]) -> dict:
        """Send a batch of tag events to the Gateway.

        Returns the JSON response: {"received": N, "accepted": N, "dropped": N}
        """
        resp = self._client.post(self.url, json=_build_payload(events))
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> dict:
        """Check Gateway health via /system/zerobus/health."""
        health_url = f"{self.base_url}/system/zerobus/health"
        resp = self._client.get(health_url)
        resp.raise_for_status()
        return resp.json()

    def configure(self, max_events_per_second: int, max_queue_size: int) -> dict | None:
        """Merge runtime config into the Gateway via GET+POST /system/zerobus/config.

        Reads the current config first. Only POSTs if the current values are
        too low, to avoid triggering unnecessary Gateway service restarts.
        """
        config_url = f"{self.base_url}/system/zerobus/config"
        current = self._client.get(config_url)
        current.raise_for_status()
        cfg = current.json()

        cur_eps = cfg.get("maxEventsPerSecond", 0)
        cur_qs = cfg.get("maxQueueSize", 0)
        if cur_eps >= max_events_per_second and cur_qs >= max_queue_size:
            return None  # already sufficient

        cfg["maxEventsPerSecond"] = max(cur_eps, max_events_per_second)
        cfg["maxQueueSize"] = max(cur_qs, max_queue_size)
        resp = self._client.post(config_url, json=cfg)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()


# Recommended batching/performance defaults for demo workloads.
# These are merged during setup so the module is ready to ingest immediately.
OPTIMIZED_DEFAULTS: dict[str, int | bool] = {
    "batchSize": 1000,
    "batchFlushIntervalMs": 500,
    "maxQueueSize": 50000,
    "maxEventsPerSecond": 5000,
    "enableStoreAndForward": False,
    "retryBackoffMs": 500,
    "connectionTimeoutMs": 10000,
    "requestTimeoutMs": 30000,
}


def setup_gateway(
    gateway_url: str,
    workspace_url: str,
    zerobus_endpoint: str,
    oauth_client_id: str,
    oauth_client_secret: str,
    target_table: str = f"{os.environ.get('CATALOG', 'agl_demo')}.{os.environ.get('SCHEMA', 'ot')}.raw_tags",
    enable_direct_subscriptions: bool = False,
    include_optimized_defaults: bool = True,
) -> dict:
    """Push Databricks connection config to the Ignition Gateway's Zerobus module.

    Reads the current config first (to preserve non-Databricks settings),
    merges in the connection fields, enables the module, and POSTs back.

    When ``include_optimized_defaults`` is True (the default), recommended
    batching and performance settings are also merged in.  Existing values
    that are *higher* than the defaults are preserved (never lowered).
    """
    base = gateway_url.rstrip("/")
    config_url = f"{base}/system/zerobus/config"

    validate_workspace_and_endpoint(workspace_url, zerobus_endpoint)

    with httpx.Client(timeout=10.0) as client:
        # Read existing config
        resp = client.get(config_url)
        resp.raise_for_status()
        cfg = resp.json()

        # Merge Databricks connection fields
        cfg["enabled"] = True
        cfg["workspaceUrl"] = workspace_url
        cfg["zerobusEndpoint"] = zerobus_endpoint
        cfg["oauthClientId"] = oauth_client_id
        cfg["oauthClientSecret"] = oauth_client_secret
        cfg["targetTable"] = target_table
        cfg["enableDirectSubscriptions"] = enable_direct_subscriptions
        # Force simplistic happy path: SDK M2M OAuth (no account-level OIDC or bearer token)
        cfg["authMode"] = "service_principal"
        cfg["accountId"] = ""

        # Merge optimized batching/performance defaults
        if include_optimized_defaults:
            for key, default_val in OPTIMIZED_DEFAULTS.items():
                if isinstance(default_val, (int, float)):
                    # Never lower an existing value — only raise to the default
                    current = cfg.get(key, 0)
                    cfg[key] = max(current, default_val)
                else:
                    # Boolean flags: set if not already present
                    if key not in cfg:
                        cfg[key] = default_val
                    else:
                        cfg[key] = default_val

        # POST updated config
        resp = client.post(config_url, json=cfg)
        resp.raise_for_status()
        return resp.json()


class AsyncGatewayClient:
    """Async version of GatewayClient using httpx.AsyncClient."""

    def __init__(self, gateway_url: str, api_key: str | None = None, timeout: float = 10.0):
        self.base_url = gateway_url.rstrip("/")
        self.url = f"{self.base_url}/system/zerobus/ingest/batch"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout)

    async def send_batch(self, events: list[TagEvent]) -> dict:
        """Send a batch of tag events to the Gateway.

        Returns the JSON response: {"received": N, "accepted": N, "dropped": N}
        """
        resp = await self._client.post(self.url, json=_build_payload(events))
        resp.raise_for_status()
        return resp.json()

    async def health_check(self) -> dict:
        """Check Gateway health via /system/zerobus/health."""
        health_url = f"{self.base_url}/system/zerobus/health"
        resp = await self._client.get(health_url)
        resp.raise_for_status()
        return resp.json()

    async def configure(self, max_events_per_second: int, max_queue_size: int) -> dict | None:
        """Merge runtime config into the Gateway via GET+POST /system/zerobus/config.

        Reads the current config first. Only POSTs if the current values are
        too low, to avoid triggering unnecessary Gateway service restarts.
        """
        config_url = f"{self.base_url}/system/zerobus/config"
        current = await self._client.get(config_url)
        current.raise_for_status()
        cfg = current.json()

        cur_eps = cfg.get("maxEventsPerSecond", 0)
        cur_qs = cfg.get("maxQueueSize", 0)
        if cur_eps >= max_events_per_second and cur_qs >= max_queue_size:
            return None  # already sufficient

        cfg["maxEventsPerSecond"] = max(cur_eps, max_events_per_second)
        cfg["maxQueueSize"] = max(cur_qs, max_queue_size)
        resp = await self._client.post(config_url, json=cfg)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
