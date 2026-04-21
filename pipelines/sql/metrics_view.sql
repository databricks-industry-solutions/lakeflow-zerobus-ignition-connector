-- Metrics view for dashboard queries
-- Creates a view over ingest_metrics for easy dashboard consumption.
-- Replace ${catalog} and ${schema} as needed.

CREATE OR REPLACE VIEW ${catalog}.${schema}.v_latest_metrics AS
SELECT
  window_start,
  window_end,
  records_raw,
  records_after_sdt,
  bytes_estimate,
  avg_latency_ms,
  p99_latency_ms,
  tags_active,
  sdt_compression_ratio,
  ROUND(records_raw - records_after_sdt, 0) AS records_saved_by_sdt
FROM ${catalog}.${schema}.ingest_metrics
WHERE window_start >= CURRENT_TIMESTAMP() - INTERVAL 5 MINUTES
ORDER BY window_start DESC;
