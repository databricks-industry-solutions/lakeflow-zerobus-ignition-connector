# Zerobus Module — Production Readiness Assessment

This document assesses the Ignition Zerobus connector module for production use and suggests improvements.

---

## Summary

The module is **suitable for production** with the following strengths. Several incremental improvements (listed below) would harden it further for high-security or high-scale deployments.

| Area | Status | Notes |
|------|--------|--------|
| Resilience | ✅ Strong | Circuit breaker, error classification, backoff, bounded shutdown |
| Store-and-forward | ✅ Strong | Disk spool, compaction, corrupt-tail recovery, backpressure |
| Configuration | ✅ Good | Validation, path auto-correct, secret preservation |
| API security | ✅ Good | Optional API key, payload limits, secret redaction |
| Observability | ⚠️ Good | Diagnostics and metrics; failures/backlog not in metrics JSON |
| Config validation | ⚠️ Good | Missing workspace/endpoint ID consistency and some bounds |
| Audit / compliance | ⚠️ Partial | No structured audit log for config changes |
| Health semantics | ⚠️ Partial | Health is “module present”, not “sink ready” |

---

## What’s Already Production-Ready

### Resilience

- **Error classification** (`ZerobusClientManager`): AUTH vs TRANSIENT vs NON_RETRIABLE with different backoff.
- **Circuit breaker**: Stops sends after repeated non-retriable errors; cooldown before probe.
- **Bounded shutdown**: Stream close runs in a background thread with a timeout so the gateway does not hang.
- **Restart**: `restartServices()` is async so the HTTP thread does not block on stream creation.

### Store-and-Forward

- **Disk spool**: Append-only format, commit-only-on-send-success, at-least-once semantics.
- **Corrupt-tail handling**: Truncates bad tail so the spool can continue without manual repair.
- **Compaction**: Reduces disk usage after consumption.
- **Backpressure**: High/low watermark; subscriptions paused when spool is full.

### Configuration

- **Validation**: When enabled, required fields and table format are validated; when disabled, partial config is allowed.
- **Path portability**: `autoCorrectPaths()` for Docker/restore; spool directory validated when SAF is enabled.
- **Secrets**: OAuth secret, bearer token, and API key preserved when UI sends masked values; redacted on GET.

### API

- **Ingest API key**: When `ingestApiKey` is set, all POST requests require `Authorization: Bearer <key>`.
- **Payload limits**: 10 MB body, 10k events per batch to avoid OOM.
- **Content-Length**: Checked before reading body in the servlet.

### Schema and Docs

- **Proto ↔ Delta**: `SCHEMA_ALIGNMENT.md` and proto comments document alignment; liquid clustering and generated columns caveats documented.

---

## Gaps and Improvement Ideas

### 1. Workspace ID vs Zerobus Endpoint Consistency (High Value)

**Gap:** A common misconfiguration is a workspace URL and Zerobus endpoint that refer to different workspaces (e.g. different IDs). Stream creation then fails (e.g. 1521) or auth fails. Validation does not check that the workspace ID implied by `workspaceUrl` matches the endpoint host.

**Idea:** In `ConfigModel.validate()`, when both `workspaceUrl` and `zerobusEndpoint` are set, extract the workspace ID from both (e.g. host segment in URL, first segment of endpoint host) and add a validation error if they differ. Reduces “wrong workspace” misconfigurations.

### 2. Observability: Failures and Buffer Backlog in Metrics (High Value)

**Gap:** `GET /system/zerobus/metrics` returns only `events_sent`, `batches_sent`, `bytes_sent`. For alerting and dashboards, `total_failures` and buffer backlog (e.g. `buffer_backlog_bytes`) are missing. Diagnostics text has them but not the JSON metrics.

**Idea:** Extend the metrics JSON with `total_failures` (from `ZerobusClientManager`) and `buffer_backlog_bytes` (from the pipeline buffer). Allows Prometheus/health checks to alert on rising failures or backlog.

### 3. Config Bounds for Queue and Rate (Medium Value)

**Gap:** `batchSize` is validated (1–10000); `maxQueueSize` and `maxEventsPerSecond` are not. Extreme values could cause OOM or confusing behavior.

**Idea:** In `ConfigModel.validate()`, add bounds (e.g. `maxQueueSize` 1–1_000_000, `maxEventsPerSecond` 1–1_000_000 or similar) and document defaults and limits in the UI/docs.

### 4. Health vs Readiness (Medium Value)

**Gap:** `GET /system/zerobus/health` returns `status: ok` and `enabled`. It does not indicate whether the sink is connected or the circuit breaker is open. For “is the gateway able to send?” you must use `/diagnostics`.

**Idea:** Either extend `/health` with optional fields (e.g. `connected`, `circuit_open`) or add a separate `GET /system/zerobus/ready` that returns 503 when the sink is not ready. Keeps liveness simple; readiness can drive load balancers or orchestration.

### 5. Structured Audit Log for Config Changes (Medium Value)

**Gap:** Config save and restart are logged as free text. Many environments need an audit trail: who changed what and when (and ideally from where). Ignition may provide identity; the module does not log config diffs or IP.

**Idea:** On save (and optionally on test-connection / restart-services), log a structured line (e.g. JSON) with timestamp, action, and which high-level fields changed (no secrets). Enables SIEM/compliance and troubleshooting.

### 6. Ingest Input Hardening (Lower Value)

**Gap:** `/ingest` and `/ingest/batch` accept arbitrary JSON for `value`. Very large or deeply nested values could stress GC or parsing. `tagPath` length is unbounded.

**Idea:** Apply reasonable limits: e.g. max length for `tagPath`, max size or depth for `value`, or reject non-primitive types. Reduces risk of DoS from buggy or malicious clients.

### 7. Version in Health or Dedicated Endpoint (Low Value)

**Gap:** Module version is in the JAR manifest and build, but not exposed via API. Ops and support often need “which version is running?” without opening the gateway UI.

**Idea:** Include `module_version` (and optionally `min_ignition_version`) in `GET /health` or add `GET /system/zerobus/version`. Simplifies support and upgrade checks.

### 8. Optional CORS (Low Value)

**Gap:** No CORS headers on API responses. The config UI is same-origin, so this is only relevant if a separate front-end (different origin) calls the gateway API.

**Idea:** If needed, add a config option (e.g. `corsAllowedOrigins`) and set CORS headers only when configured. Default remains no CORS.

---

## Recommended Order of Work

1. **Workspace/endpoint validation** and **metrics (failures + backlog)** — high impact, low risk.
2. **Config bounds** for `maxQueueSize` and `maxEventsPerSecond` — quick and prevents misuse.
3. **Health/readiness** and **audit logging** — depends on how strictly you need orchestration and compliance.
4. **Ingest limits**, **version endpoint**, **CORS** — as needed for your environment.

---

## Testing and Upgrade

- **Unit tests** cover ConfigModel, StoreAndForwardBuffer, DiskSpool, and SDT components. Adding tests for new validation rules and for servlet handler (e.g. API key, payload limits) would strengthen regression safety.
- **Upgrade path**: Module ID is stable; config is persisted via Ignition’s PersistentRecord. After upgrading the .modl, restart the gateway and re-run validation (e.g. Test Connection). If you introduce a new required config field, consider a one-time migration or clear documentation for existing users.

---

*Last updated: 2026-02-15*
