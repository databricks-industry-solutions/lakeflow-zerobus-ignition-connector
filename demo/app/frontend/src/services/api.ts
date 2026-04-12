const API_BASE = import.meta.env.VITE_API_URL ?? "";

interface ApiResponse<T> {
  data: T;
  meta: { timestamp: string; query_time_ms: number; error?: string };
}

async function fetchJson<T>(path: string): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    // 502 = QueryError from backend; body contains {data, meta} with meta.error
    if (res.status === 502) {
      const body = (await res.json()) as ApiResponse<T>;
      throw new Error(body.meta?.error ?? `Query failed (${res.status})`);
    }
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<ApiResponse<T>>;
}

async function postJson<T>(
  path: string,
  body: unknown,
): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    if (res.status === 502) {
      const errBody = (await res.json()) as ApiResponse<T>;
      throw new Error(errBody.meta?.error ?? `Query failed (${res.status})`);
    }
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<ApiResponse<T>>;
}

async function putJson<T>(
  path: string,
  body: unknown,
): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    if (res.status === 502) {
      const errBody = (await res.json()) as ApiResponse<T>;
      throw new Error(errBody.meta?.error ?? `Query failed (${res.status})`);
    }
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<ApiResponse<T>>;
}

async function deleteJson<T>(path: string): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    if (res.status === 502) {
      const errBody = (await res.json()) as ApiResponse<T>;
      throw new Error(errBody.meta?.error ?? `Query failed (${res.status})`);
    }
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<ApiResponse<T>>;
}

export interface ThroughputMetric {
  window_start: string;
  window_end: string;
  records_raw: number;
  records_after_sdt: number;
  bytes_estimate: number;
  tags_active: number;
  sdt_compression_ratio: number;
  /** Gateway config: SDT was on when events in this window were sent (from connector). */
  sdt_enabled?: boolean;
}

export interface LatencyMetric {
  window_start: string;
  window_end: string;
  avg_latency_ms: number;
  p99_latency_ms: number;
  /** E2E: tag time → Delta commit (from CDF _commit_timestamp), when available. */
  avg_e2e_latency_ms?: number;
  p99_e2e_latency_ms?: number;
  /** Time from Delta commit visibility to app query-time (freshness proxy). */
  avg_delta_to_app_ms?: number;
  p99_delta_to_app_ms?: number;
}

export interface TagEvent {
  event_timestamp: string;
  ingest_timestamp: string;
  asset_id: string;
  asset_type: string;
  tag_name: string;
  tag_value: number;
  quality: number;
  sdt_compressed: boolean;
  compression_ratio: number;
}

export interface Asset {
  asset_id: string;
  asset_name: string;
  asset_type: string;
  site_name: string;
  capacity_mw: number;
  tag_count: number;
  latitude?: number;
  longitude?: number;
  operational_state?: string;
  alarm_code?: number | string;
  last_update?: string;
  compression_ratio?: number;
  commissioned_date?: string;
}

export interface TagHistory {
  event_timestamp: string;
  tag_name: string;
  tag_value: number;
  quality: number;
  sdt_compressed: boolean;
}

export interface SdtConfigEntry {
  tag_pattern: string;
  comp_dev: number | null;
  comp_dev_percent: number | null;
  comp_max_seconds: number;
  comp_min_seconds: number;
}

// Asset Framework types
export interface HierarchyAsset {
  asset_id: string;
  parent_asset_id: string | null;
  asset_name: string;
  asset_type: string;
  template_id: string | null;
  site_name: string | null;
  description: string | null;
  capacity_mw?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  tag_count?: number | null;
  depth: number;
  child_count: number;
  active?: boolean;
  template_name?: string | null;
  template_base_type?: string | null;
}

export interface AssetTemplate {
  template_id: string;
  template_name: string;
  description: string | null;
  base_asset_type: string;
  attribute_count: number;
  asset_count: number;
}

export interface TemplateAttribute {
  attribute_id: string;
  attribute_name: string;
  data_type: string;
  unit: string | null;
  default_value: string | null;
  is_required: boolean;
  sort_order: number;
}

export interface TemplateDetailRow {
  template_id: string;
  template_name: string;
  description: string | null;
  base_asset_type: string;
  attribute_id: string | null;
  attribute_name: string | null;
  data_type: string | null;
  unit: string | null;
  default_value: string | null;
  is_required: boolean | null;
  sort_order: number | null;
  tag_pattern: string | null;
}

export interface TemplateDetail {
  template: TemplateDetailRow[];
  assets: {
    asset_id: string;
    asset_name: string;
    asset_type: string;
    site_name: string;
  }[];
}

// Analytics (health scores + revenue at risk)
export interface HealthScoreRow {
  scored_at: string;
  asset_id: string;
  health_score: number;
  primary_risk_tag: string | null;
  risk_description: string | null;
  anomaly_tags: string[] | null;
  estimated_hours_to_failure: number | null;
}

export interface RevenueRiskRow {
  computed_at: string;
  asset_id: string;
  risk_window_start: string;
  risk_window_end: string;
  forecast_price_aud_mwh: number;
  asset_capacity_mw: number;
  health_score: number | null;
  trip_probability: number;
  revenue_at_risk_aud: number;
  recommended_action: string;
}

export interface RevenueSummary {
  assets_at_risk: number;
  total_revenue_at_risk_aud: number;
  avg_health_score: number | null;
  next_risk_window: string | null;
}

export interface NemSnapshotRow {
  region_id: string;
  price_timestamp: string;
  rrp: number;
  total_demand_mw: number;
  available_generation_mw: number;
  net_interchange_mw: number;
}

export interface BomCurrentRow {
  station_name: string;
  air_temp_c: number | null;
  apparent_temp_c: number | null;
  relative_humidity_pct: number | null;
  wind_speed_kmh: number | null;
  wind_direction: string | null;
  rainfall_mm: number | null;
  observation_timestamp: string | null;
}

export interface AssetAttributeValue {
  attribute_id: string;
  attribute_name: string;
  data_type: string;
  unit: string | null;
  is_required: boolean;
  value: string | null;
  updated_at: string | null;
  tag_pattern: string | null;
}

export interface LiveAttributeValue {
  attribute_id: string;
  attribute_name: string;
  tag_pattern: string;
  live_value: number | null;
  live_at: string | null;
}

export interface AssetTagCatalogRow {
  asset_id: string;
  tag_name: string;
  tag_path: string | null;
  unit: string | null;
  source_domain: string | null;
  is_mapped: boolean;
  live_value: number | null;
  live_value_str: string | null;
  quality: number | null;
  live_at: string | null;
  sdt_compressed: boolean | null;
  compression_ratio: number | null;
}

export interface AssetTagSummaryRow {
  asset_id: string;
  mapped_tag_count: number;
  live_tag_count: number;
  mapped_live_tag_count: number;
  unmapped_tag_count: number;
}

export interface ChildAggregationRow {
  tag_name: string;
  avg_value: number;
  min_value: number;
  max_value: number;
  asset_count: number;
}

export interface DiagnosticData {
  total_rows: string;
  rows_last_10_min: string;
  oldest_event: string | null;
  newest_event: string | null;
  warehouse_now: string;
}

export interface PostgresDiagnosticData {
  configured: boolean;
  total_rows?: number;
  rows_last_10_min?: number;
  oldest_event?: string | null;
  newest_event?: string | null;
  db_now?: string | null;
  message?: string;
  error?: string;
}

export interface PostgresHealthData {
  status: string;
  host?: string;
  database?: string;
  table?: string;
  pool_size?: number;
  pool_free?: number;
  message?: string;
  error?: string;
}

export const api = {
  getThroughput: (
    source: "raw_tags" | "raw_throughput" = "raw_tags",
    minutes = 5,
  ) =>
    fetchJson<ThroughputMetric[]>(
      `/api/metrics/throughput?source=${source}&minutes=${minutes}`,
    ),
  getLatency: (
    source: "raw_tags" | "raw_throughput" = "raw_tags",
    minutes = 5,
  ) =>
    fetchJson<LatencyMetric[]>(
      `/api/metrics/latency?source=${source}&minutes=${minutes}`,
    ),
  getDiagnostic: () => fetchJson<DiagnosticData>("/api/metrics/diagnostic"),
  getCompression: () => fetchJson<unknown[]>("/api/metrics/compression"),
  getEventsLatest: (limit = 50) =>
    fetchJson<TagEvent[]>(`/api/events/latest?limit=${limit}`),
  getAssets: () => fetchJson<Asset[]>("/api/assets"),
  getAsset: (id: string) => fetchJson<Asset>(`/api/assets/${id}`),
  getAssetTags: (id: string, tags?: string[], range = 5) => {
    const params = new URLSearchParams();
    if (tags?.length) params.set("tags", tags.join(","));
    params.set("range", String(range));
    return fetchJson<TagHistory[]>(`/api/assets/${id}/tags?${params}`);
  },
  getCompressionComparison: () =>
    fetchJson<unknown>("/api/compression/comparison"),
  getSdtConfig: () =>
    fetchJson<SdtConfigEntry[]>("/api/compression/sdt-config"),
  updateSdtConfig: (
    config: Partial<SdtConfigEntry> & { tag_pattern: string },
  ) => putJson<SdtConfigEntry[]>("/api/compression/sdt-config", config),
  getScenario: () => fetchJson<{ scenario: string }>("/api/config/scenario"),
  setScenario: (scenario: string) =>
    postJson<{ scenario: string }>("/api/config/scenario", { scenario }),
  resetDemo: () => postJson<{ status: string }>("/api/admin/reset", {}),

  // Analytics (fleet health & revenue at risk)
  getHealthScores: () =>
    fetchJson<HealthScoreRow[]>("/api/analytics/health-scores"),
  getRevenueRisk: () =>
    fetchJson<RevenueRiskRow[]>("/api/analytics/revenue-risk"),
  getRevenueSummary: () =>
    fetchJson<RevenueSummary>("/api/analytics/revenue-summary"),

  // Time Travel / Historical Replay
  getAssetTagsRange: (id: string, from: string, to: string, resolution?: string, tags?: string[]) => {
    const params = new URLSearchParams({ from, to });
    if (resolution) params.set("resolution", resolution);
    if (tags?.length) params.set("tags", tags.join(","));
    return fetchJson<TagHistory[]>(`/api/assets/${id}/tags?${params}`);
  },
  getFleetSnapshot: (timestamp: string) =>
    fetchJson<HealthScoreRow[]>(`/api/fleet/snapshot?timestamp=${encodeURIComponent(timestamp)}`),
  exportAssetTagsCsv: async (id: string, from: string, to: string): Promise<void> => {
    const params = new URLSearchParams({ from, to, format: "csv" });
    const apiBase = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) ?? "";
    const url = `${apiBase}/api/assets/${id}/tags/export?${params}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Export failed: ${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const cd = res.headers.get("Content-Disposition") ?? "";
    const m = cd.match(/filename="?([^"]+)"?/);
    a.download = m ? m[1] : `${id}_export.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  },
  getForensics: (id: string, eventTime: string, windowMinutes = 30) =>
    fetchJson<TagHistory[]>(`/api/assets/${id}/forensics?event_time=${encodeURIComponent(eventTime)}&window_minutes=${windowMinutes}`),

  // Market & Weather (Databricks 101 demo)
  marketWeather: {
    getBomCurrent: () =>
      fetchJson<BomCurrentRow[]>('/api/market-weather/bom/current'),
    getBomDaily: () =>
      fetchJson<unknown[]>('/api/market-weather/bom/daily'),
    getNemSnapshot: () =>
      fetchJson<NemSnapshotRow[]>('/api/market-weather/nem/snapshot'),
    getNemPrices: (hours = 6) =>
      fetchJson<unknown[]>(`/api/market-weather/nem/prices?hours=${hours}`),
  },

  // Asset Framework
  assetFramework: {
    getHierarchy: () =>
      fetchJson<HierarchyAsset[]>("/api/asset-framework/hierarchy"),
    getAsset: (id: string) =>
      fetchJson<HierarchyAsset>(`/api/asset-framework/hierarchy/${id}`),
    createAsset: (body: {
      asset_id: string;
      asset_name: string;
      asset_type: string;
      parent_asset_id?: string | null;
      template_id?: string | null;
      site_name?: string | null;
      description?: string | null;
      capacity_mw?: number | null;
      latitude?: number | null;
      longitude?: number | null;
      tag_count?: number | null;
    }) => postJson<HierarchyAsset>("/api/asset-framework/hierarchy", body),
    updateAsset: (
      id: string,
      body: {
        asset_name?: string;
        asset_type?: string;
        template_id?: string;
        site_name?: string;
        description?: string;
        capacity_mw?: number | null;
        latitude?: number | null;
        longitude?: number | null;
        tag_count?: number | null;
      },
    ) => putJson<HierarchyAsset>(`/api/asset-framework/hierarchy/${id}`, body),
    deleteAsset: (id: string) =>
      deleteJson<{ deleted: string }>(`/api/asset-framework/hierarchy/${id}`),
    moveAsset: (id: string, newParentId: string | null) =>
      putJson<HierarchyAsset>(`/api/asset-framework/hierarchy/${id}/move`, {
        new_parent_id: newParentId,
      }),
    applyTemplate: (id: string, templateId: string) =>
      postJson<AssetAttributeValue[]>(
        `/api/asset-framework/hierarchy/${id}/apply-template`,
        { template_id: templateId },
      ),
    getAssetAttributes: (id: string) =>
      fetchJson<AssetAttributeValue[]>(
        `/api/asset-framework/hierarchy/${id}/attributes`,
      ),
    getLiveAttributes: (id: string) =>
      fetchJson<LiveAttributeValue[]>(
        `/api/asset-framework/hierarchy/${id}/live-attributes`,
      ),
    getAssetTags: (id: string, minutes = 60, includeUnmapped = true) =>
      fetchJson<AssetTagCatalogRow[]>(
        `/api/asset-framework/hierarchy/${id}/tags?minutes=${minutes}&include_unmapped=${includeUnmapped}`,
      ),
    getTagSummary: (minutes = 60) =>
      fetchJson<AssetTagSummaryRow[]>(
        `/api/asset-framework/hierarchy/tag-summary?minutes=${minutes}`,
      ),
    getChildAggregation: (id: string, minutes = 10) =>
      fetchJson<ChildAggregationRow[]>(
        `/api/asset-framework/hierarchy/${id}/aggregation?minutes=${minutes}`,
      ),
    updateAssetAttributes: (
      id: string,
      values: { attribute_id: string; value: string | null }[],
    ) =>
      putJson<AssetAttributeValue[]>(
        `/api/asset-framework/hierarchy/${id}/attributes`,
        { values },
      ),

    getTemplates: () =>
      fetchJson<AssetTemplate[]>("/api/asset-framework/templates"),
    getTemplate: (id: string) =>
      fetchJson<TemplateDetail>(`/api/asset-framework/templates/${id}`),
    createTemplate: (body: {
      template_id: string;
      template_name: string;
      base_asset_type: string;
      description?: string | null;
    }) => postJson<TemplateDetailRow[]>("/api/asset-framework/templates", body),
    updateTemplate: (
      id: string,
      body: {
        template_name?: string;
        description?: string;
        base_asset_type?: string;
      },
    ) =>
      putJson<TemplateDetailRow[]>(
        `/api/asset-framework/templates/${id}`,
        body,
      ),
    deleteTemplate: (id: string) =>
      deleteJson<{ deleted: string }>(`/api/asset-framework/templates/${id}`),
    createAttribute: (
      templateId: string,
      body: {
        attribute_id: string;
        attribute_name: string;
        data_type: string;
        unit?: string | null;
        default_value?: string | null;
        is_required?: boolean;
        sort_order?: number;
        tag_pattern?: string | null;
      },
    ) =>
      postJson<TemplateDetailRow[]>(
        `/api/asset-framework/templates/${templateId}/attributes`,
        body,
      ),
    updateAttribute: (
      templateId: string,
      attrId: string,
      body: {
        attribute_name?: string;
        data_type?: string;
        unit?: string | null;
        default_value?: string | null;
        is_required?: boolean;
        sort_order?: number;
        tag_pattern?: string | null;
      },
    ) =>
      putJson<TemplateDetailRow[]>(
        `/api/asset-framework/templates/${templateId}/attributes/${attrId}`,
        body,
      ),
    deleteAttribute: (templateId: string, attrId: string) =>
      deleteJson<TemplateDetailRow[]>(
        `/api/asset-framework/templates/${templateId}/attributes/${attrId}`,
      ),
  },

  // PostgreSQL (Lakebase) metrics
  postgres: {
    getHealth: () =>
      fetchJson<PostgresHealthData>("/api/postgres-metrics/health"),
    getThroughput: (minutes = 5) =>
      fetchJson<ThroughputMetric[]>(
        `/api/postgres-metrics/throughput?minutes=${minutes}`,
      ),
    getLatency: (minutes = 5) =>
      fetchJson<LatencyMetric[]>(
        `/api/postgres-metrics/latency?minutes=${minutes}`,
      ),
    getEventsLatest: (limit = 50) =>
      fetchJson<TagEvent[]>(
        `/api/postgres-metrics/events/latest?limit=${limit}`,
      ),
    getDiagnostic: () =>
      fetchJson<PostgresDiagnosticData>("/api/postgres-metrics/diagnostic"),
  },
};

// Top-level re-exports so tests can check `typeof getFleetSnapshot` on the module
export const getFleetSnapshot = api.getFleetSnapshot;
export const exportAssetTagsCsv = api.exportAssetTagsCsv;
