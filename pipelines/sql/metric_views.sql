-- Unity Catalog Metric Views for AGL Fleet Operations
-- Requires DBR 17.2+ and a SQL warehouse.
-- Placeholders __CATALOG__ and __SCHEMA__ are replaced by run_setup_sql.py.
--
-- Metric views define measures once and let users slice by any dimension
-- at query time — ideal for Genie spaces, AI/BI dashboards, and alerts.

-- ============================================================================
-- 1. Fleet Operations Metric View
--    Source: enriched_tags (1-minute windowed OT aggregations with asset context)
--    Use cases: Genie "show me avg temperature by asset", dashboard KPI tiles,
--               alerts on signal anomalies
-- ============================================================================
CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.fleet_operations_metrics
WITH METRICS
LANGUAGE YAML
AS $$
  version: 1.1
  comment: "Fleet operations KPIs across all OT assets — signal health, throughput, and variability"
  source: __CATALOG__.__SCHEMA__.enriched_tags
  filter: window_start >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS

  dimensions:
    - name: Asset
      expr: asset_id
      comment: "Unique asset identifier (e.g. tomago_bess01, hexham_t01)"

    - name: Signal
      expr: signal_name
      comment: "Measurement signal path (e.g. battery/soc_pct, generator/speed_rpm)"

    - name: Unit
      expr: unit
      comment: "Engineering unit (%, RPM, °C, MW, etc.)"

    - name: Source Domain
      expr: source_domain
      comment: "OT domain grouping (battery, generator, grid, market, maintenance)"

    - name: Hour
      expr: DATE_TRUNC('HOUR', window_start)
      comment: "Hourly time bucket"

    - name: Minute
      expr: window_start
      comment: "1-minute window start (native grain)"

  measures:
    - name: Avg Value
      expr: AVG(avg_value)
      comment: "Mean signal value across selected windows"

    - name: Peak Value
      expr: MAX(max_value)
      comment: "Highest observed signal value"

    - name: Min Value
      expr: MIN(min_value)
      comment: "Lowest observed signal value"

    - name: Total Samples
      expr: SUM(sample_count)
      comment: "Total raw data points before aggregation"

    - name: Active Signals
      expr: COUNT(DISTINCT signal_name)
      comment: "Number of distinct signals reporting"

    - name: Active Assets
      expr: COUNT(DISTINCT asset_id)
      comment: "Number of distinct assets reporting"

    - name: Avg Variability
      expr: AVG(stddev_value)
      comment: "Mean standard deviation — higher values indicate instability"

    - name: Signal Windows
      expr: COUNT(1)
      comment: "Number of 1-minute aggregation windows"

    - name: Samples per Window
      expr: SUM(sample_count) / NULLIF(COUNT(1), 0)
      comment: "Average data density per 1-minute window"
$$;


-- ============================================================================
-- 2. Ingest Platform Metric View
--    Source: raw_tags (Zerobus connector landing table, event-level grain)
--    Use cases: Platform health monitoring, SLA dashboards, compression analysis
-- ============================================================================
CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.ingest_platform_metrics
WITH METRICS
LANGUAGE YAML
AS $$
  version: 1.1
  comment: "Zerobus ingest platform KPIs — throughput, latency, and SDT compression effectiveness"
  source: __CATALOG__.__SCHEMA__.raw_tags
  filter: ingestion_timestamp > (UNIX_MICROS(CURRENT_TIMESTAMP()) - 3600000000)

  dimensions:
    - name: Minute
      expr: DATE_TRUNC('MINUTE', TO_TIMESTAMP(ingestion_timestamp / 1000000))
      comment: "Per-minute ingest time bucket"

    - name: Tag Provider
      expr: tag_provider
      comment: "Ignition tag provider (e.g. agl_bess, agl_wind)"

    - name: Source System
      expr: source_system
      comment: "Source identifier (e.g. ignition_sim)"

    - name: SDT Compressed
      expr: CASE WHEN sdt_compressed THEN 'Compressed' ELSE 'Raw' END
      comment: "Whether event survived SDT compression filter"

  measures:
    - name: Total Events
      expr: COUNT(1)
      comment: "Total events landing in raw_tags"

    - name: Events After SDT
      expr: COUNT(1) FILTER (WHERE sdt_compressed = true)
      comment: "Events that survived SDT compression"

    - name: Events Filtered by SDT
      expr: COUNT(1) FILTER (WHERE sdt_compressed = false)
      comment: "Events eliminated by Swinging Door Trending"

    - name: SDT Savings Pct
      expr: 100.0 * COUNT(1) FILTER (WHERE sdt_compressed = false) / NULLIF(COUNT(1), 0)
      comment: "Percentage of events filtered by SDT compression"

    - name: Avg Compression Ratio
      expr: AVG(compression_ratio) FILTER (WHERE compression_ratio IS NOT NULL AND compression_ratio > 0)
      comment: "Mean running compression ratio across tags"

    - name: Avg Latency ms
      expr: AVG((ingestion_timestamp - event_time) / 1000.0)
      comment: "Mean end-to-end latency in ms (Ignition event to Delta ingest)"

    - name: P95 Latency ms
      expr: PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (ingestion_timestamp - event_time) / 1000.0)
      comment: "95th percentile end-to-end latency in ms"

    - name: Active Tags
      expr: COUNT(DISTINCT tag_path)
      comment: "Number of distinct tag paths reporting"

    - name: Bytes Sent
      expr: SUM(batch_bytes_sent)
      comment: "Total bytes sent across batches"

    - name: Good Quality Pct
      expr: 100.0 * COUNT(1) FILTER (WHERE quality_code = 192) / NULLIF(COUNT(1), 0)
      comment: "Percentage of events with OPC Good quality (code 192)"
$$;
