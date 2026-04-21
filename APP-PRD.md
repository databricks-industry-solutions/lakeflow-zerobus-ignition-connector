# APP-PRD.md — AGL Revenue-at-Risk Monitor (Databricks App)

> **This document is the single source of truth for a Claude Code Ralph Loop.**
> Iterate through all requirements (`FR-*`, `NFR-*`) until every acceptance criterion (`AC-*`) is satisfied.
> When all work is complete and verified, output `<promise>DONE</promise>`.

---

## Meta

| Field | Value |
|---|---|
| Product | AGL Revenue-at-Risk Monitor |
| Deploy target | Databricks App (serverless, Azure `australiaeast`) |
| Stack | Python 3.11+, FastAPI, React 18+, Vite, Tailwind CSS, Recharts/Tremor, `databricks-sql-connector` |
| Data source | Delta tables populated by Zerobus ingest (see companion `PRD.md`) + AEMO public NEM price data |
| Target audience | John Bruzzaniti — Head of Asset Intelligence, AGL Energy |

---

## 1 · Why this app exists

### The business problem (not an IT problem)

AGL makes money in the NEM by having assets **available when prices spike**. This is the entire economics of their new battery and wind fleet:

- **Battery revenue model**: Buy electricity when cheap ($30–80/MWh), sell when expensive ($300–$17,500/MWh). A 500 MW battery earns ~$62k/MW/year — almost all of it concentrated in a few hundred hours of price spikes. If the battery is offline during those hours, the revenue is gone forever.
- **Wind revenue model**: Generate and sell into high-price periods. Unplanned downtime during a summer heatwave spike (prices regularly hit $5,000–$17,500/MWh) costs orders of magnitude more than downtime during low-price periods.

**The asset intelligence question that matters is not "will this asset fail?" — it's "will this asset fail before the next price event?"**

Traditional historian + predictive analytics stacks often cannot answer this question because:

| Limitation | Why it matters |
|---|---|
| **Historian disconnected from market data** | Historians store OT data. NEM prices live in AEMO feeds. There is often no concept of "this anomaly matters more at 4pm tomorrow than at 3am." No revenue-weighted risk view. |
| **Closed-box predictive analytics** | Many stacks train models on historian data in a closed ML engine. You cannot join a bearing temperature prediction with a NEM price forecast in the same query. You cannot run your own models. You cannot enrich with weather, market, or financial data. |
| **Per-tag licensing kills high-resolution economics** | Per-tag licensing at 2M+ tags means increasing resolution from 5-min to 1-sec multiplies cost. So many sites run at 5-min resolution, meaning anomalies are detected later, meaning more risk during price events. |
| **New asset onboarding takes weeks** | Every new battery or wind site often needs dedicated historian infrastructure. During those weeks, the asset operates without health monitoring — flying blind during potential price spikes. |
| **No unified view across OT + market** | Process trends live in one place; market and revenue impact in another. No single view of "this turbine's gearbox is degrading AND tomorrow's price forecast is $8,000/MWh AND the cost of losing this 5 MW turbine during that window is $40,000/hour." |

### What the lakehouse unlocks

On Databricks, the OT tag data (via Zerobus) and AEMO market data land in the **same Delta tables under the same Unity Catalog**. This means:

- One SQL query can join a bearing temperature anomaly score with tomorrow's price forecast
- Models are trained in Python/MLflow on the same platform — not in a closed ML box
- New assets are monitored within minutes of Zerobus config, not weeks of historian provisioning
- 1-second resolution costs the same as 5-minute (because Delta + SDT compression, not per-tag licensing)
- John's data scientists — who already know Python and SQL — can build and iterate, not wait for vendor PS engagements

---

## 2 · Solution overview

### What the app does in one sentence

**A Databricks App that shows which AGL assets are at risk of tripping offline before the next high-price NEM event, and quantifies the revenue at stake.**

### Architecture

```
┌─────────────────────────┐     ┌─────────────────────────┐
│  Zerobus Ingest          │     │  AEMO Public Data        │
│  (wind/battery OT tags)  │     │  (dispatch prices, CSV)  │
└──────────┬──────────────┘     └──────────┬──────────────┘
           │                                │
           ▼                                ▼
┌─────────────────────────────────────────────────────────┐
│  Delta Tables (Unity Catalog)                            │
│                                                          │
│  agl_demo.ot.raw_tags          ← OT tag data            │
│  agl_demo.ot.ingest_metrics    ← throughput/latency      │
│  agl_demo.market.nem_prices    ← 5-min dispatch prices   │
│  agl_demo.market.price_forecast← 48hr price forecast     │
│  agl_demo.analytics.health_scores ← computed per asset   │
│  agl_demo.analytics.revenue_risk  ← risk = health × price│
└──────────┬──────────────────────────────────────────────┘
           │ Databricks SQL Warehouse
           ▼
┌─────────────────────────┐
│  Databricks App          │
│  (FastAPI / React)       │
│  Revenue-at-Risk Monitor │
└─────────────────────────┘
```

### Key tables (in addition to companion PRD tables)

#### `agl_demo.market.nem_prices`

| Column | Type | Description |
|---|---|---|
| `interval_start` | `TIMESTAMP` | 5-min dispatch interval start |
| `interval_end` | `TIMESTAMP` | 5-min dispatch interval end |
| `region` | `STRING` | NEM region (`NSW1`, `VIC1`, `QLD1`, `SA1`, `TAS1`) |
| `price_aud_mwh` | `DOUBLE` | Regional reference price ($/MWh) |
| `demand_mw` | `DOUBLE` | Regional demand |

#### `agl_demo.market.price_forecast`

| Column | Type | Description |
|---|---|---|
| `forecast_timestamp` | `TIMESTAMP` | When forecast was generated |
| `target_interval` | `TIMESTAMP` | Future interval being forecast |
| `region` | `STRING` | NEM region |
| `forecast_price_aud_mwh` | `DOUBLE` | Predicted price |
| `confidence` | `STRING` | `high` / `medium` / `low` |

#### `agl_demo.analytics.health_scores`

| Column | Type | Description |
|---|---|---|
| `scored_at` | `TIMESTAMP` | When score was computed |
| `asset_id` | `STRING` | FK to assets table |
| `health_score` | `DOUBLE` | 0.0 (critical) to 1.0 (healthy) |
| `primary_risk_tag` | `STRING` | Tag driving the risk (e.g., `nacelle/temperature_c`) |
| `risk_description` | `STRING` | Human-readable risk summary |
| `anomaly_tags` | `ARRAY<STRING>` | All tags currently anomalous |
| `estimated_hours_to_failure` | `DOUBLE` | Nullable — rough estimate if degradation trend detected |

#### `agl_demo.analytics.revenue_risk`

| Column | Type | Description |
|---|---|---|
| `computed_at` | `TIMESTAMP` | When computed |
| `asset_id` | `STRING` | FK to assets table |
| `risk_window_start` | `TIMESTAMP` | Start of high-price window |
| `risk_window_end` | `TIMESTAMP` | End of high-price window |
| `forecast_price_aud_mwh` | `DOUBLE` | Expected price during window |
| `asset_capacity_mw` | `DOUBLE` | Asset rated capacity |
| `health_score` | `DOUBLE` | Current health score |
| `trip_probability` | `DOUBLE` | Estimated probability of trip (0–1) |
| `revenue_at_risk_aud` | `DOUBLE` | capacity × hours × price × trip_probability |
| `recommended_action` | `STRING` | Human-readable recommendation |

---

## 3 · Phased implementation plan

### Phase 1 — Data layer and market data
`FR-100` through `FR-104`

### Phase 2 — Health scoring engine
`FR-105` through `FR-108`

### Phase 3 — Revenue-at-risk computation
`FR-109` through `FR-112`

### Phase 4 — Frontend: Revenue-at-Risk Monitor
`FR-113` through `FR-121`

### Phase 5 — Databricks App packaging and demo readiness
`FR-122` through `FR-126`

---

## 4 · Functional requirements

### Phase 1 — Data layer and market data

**FR-100: Additional table setup**
The system shall extend the companion PRD's `setup_tables.sql` (or create `setup_app_tables.sql`) to create all tables from Section 2 (market + analytics schemas).

- **AC-100-1**: Script is idempotent.
- **AC-100-2**: Tables created under `agl_demo.market` and `agl_demo.analytics`.

**FR-101: AEMO price data loader**
The system shall include a script that loads historical NEM dispatch price data from AEMO public CSV files into `nem_prices`.

- **AC-101-1**: Script downloads from `https://aemo.com.au` public dispatch price archive (CSV format).
- **AC-101-2**: Loads at least 30 days of 5-minute dispatch prices for NSW1 region (AGL's primary).
- **AC-101-3**: Deduplicates on re-run.

**FR-102: Price forecast simulator**
The system shall generate synthetic 48-hour price forecasts into `price_forecast`:
- Base pattern: follow historical daily shape (low overnight $30–80, morning ramp, afternoon peak)
- Inject 2–3 "spike events" per day during peak hours (4–7pm) with prices $2,000–$15,000/MWh
- Vary by day to make the demo dynamic

- **AC-102-1**: Forecast regenerates on a schedule or on-demand via API.
- **AC-102-2**: At least one spike event falls within the next 24 hours so the demo always has urgency.

**FR-103: Simulated asset fleet**
The system shall configure a realistic AGL fleet in the `assets` table:

| Site | Type | Count | Capacity each | Region |
|---|---|---|---|---|
| Hexham | Wind turbine | 50 | 12 MW | NSW1 |
| Pottinger | Wind turbine | 40 | 12 MW | NSW1 |
| Liddell Battery | BESS | 20 | 25 MW | NSW1 |
| Tomago Battery | BESS | 15 | 33 MW | NSW1 |
| Broken Hill Battery | BESS | 10 | 5 MW | NSW1 |

- **AC-103-1**: Assets table populated with lat/long coordinates near actual AGL site locations.
- **AC-103-2**: Tag counts per asset match profiles from companion PRD.

**FR-104: Backend API server**
The system shall create a FastAPI server with endpoints specific to the revenue-at-risk app.

- **AC-104-1**: Runs on configurable port via `DATABRICKS_APP_PORT` environment variable.
- **AC-104-2**: Uses `databricks-sql-connector` with connection pooling.

---

### Phase 2 — Health scoring engine

**FR-105: Simple anomaly detection**
The system shall compute health scores per asset using a **z-score based anomaly detection** on key tags:
- For each asset, maintain a rolling 1-hour mean and stddev per key tag
- Key tags for wind: `nacelle/temperature_c`, `generator/power_kw` (vs wind speed expected), `grid/frequency_hz`
- Key tags for battery: `battery/temperature_c`, `battery/soc_pct` (vs expected cycle), `thermal/coolant_temp_c`
- A tag is "anomalous" if its current value exceeds 2σ from rolling mean
- Health score = 1.0 - (anomalous_tag_count / total_key_tag_count), clamped to [0, 1]

- **AC-105-1**: Implemented as a SQL view or lightweight scheduled query that writes to `health_scores`.
- **AC-105-2**: Scores recomputed every 30 seconds (or on API call for demo).
- **AC-105-3**: `primary_risk_tag` is the tag with the highest z-score deviation.

**FR-106: Degradation scenario injection**
The simulator (from companion PRD) shall support injecting degradation scenarios:
- "Gearbox bearing overheat" — `nacelle/temperature_c` slowly drifts +0.5°C/minute for a target turbine
- "Battery thermal runaway warning" — `thermal/coolant_temp_c` diverges from `battery/temperature_c` by increasing delta
- "Inverter efficiency drop" — `inverter/efficiency_pct` decays linearly

- **AC-106-1**: Scenarios triggered via `POST /api/scenarios/inject` with `{ asset_id, scenario_type, duration_minutes }`.
- **AC-106-2**: Degradation is visible in health score within 2 minutes of injection.
- **AC-106-3**: At least one degradation is auto-injected at demo start so there's always something to show.

**FR-107: Health score API**
The system shall expose:
- `GET /api/health/fleet` — all assets with current health scores
- `GET /api/health/:assetId` — single asset health detail with anomalous tags
- `GET /api/health/:assetId/history?range=<minutes>` — health score over time

- **AC-107-1**: Fleet endpoint returns data sorted by health score ascending (worst first).
- **AC-107-2**: Response time < 2 seconds.

**FR-108: Comparison data point (traditional vs lakehouse)**
The system shall compute and expose a "detection speed comparison":
- Given the degradation rate, calculate: "At 5-min resolution (PI), this anomaly would be detectable at time T₁. At 1-sec resolution (lakehouse), detectable at T₂."
- Time-to-detection = time until z-score > 2σ at each resolution

- **AC-108-1**: Exposed via `GET /api/health/:assetId/detection-comparison`.
- **AC-108-2**: Returns `{ pi_detection_minutes, lakehouse_detection_minutes, improvement_factor }`.

---

### Phase 3 — Revenue-at-risk computation

**FR-109: Revenue-at-risk calculator**
The system shall compute revenue at risk for each asset:
```
revenue_at_risk = asset_capacity_mw × window_hours × forecast_price_aud_mwh × trip_probability
```
Where:
- `trip_probability` = `1.0 - health_score` (simple mapping for demo)
- Window = next forecast period where price > $300/MWh (the threshold for "high price event")

- **AC-109-1**: Written to `revenue_risk` table, recomputed every 60 seconds.
- **AC-109-2**: `recommended_action` is rule-based:
  - health > 0.8: "Monitor — no action needed"
  - health 0.5–0.8: "Schedule inspection before [window_start]"
  - health 0.3–0.5: "Urgent: schedule maintenance tonight"
  - health < 0.3: "Critical: consider preemptive shutdown and repair to protect fleet"

**FR-110: Fleet revenue-at-risk summary**
The system shall compute fleet-level aggregates:
- Total revenue at risk across all assets for next 24h
- Revenue at risk by site
- Revenue at risk by asset type

- **AC-110-1**: Exposed via `GET /api/risk/fleet-summary`.
- **AC-110-2**: Returns breakdowns by site and asset type.

**FR-111: Revenue-at-risk API**
| Method | Path | Description |
|---|---|---|
| GET | `/api/risk/fleet-summary` | Fleet-level revenue risk |
| GET | `/api/risk/assets` | All assets with revenue risk, sorted by risk descending |
| GET | `/api/risk/:assetId` | Single asset risk detail |
| GET | `/api/market/prices/current` | Recent NEM prices |
| GET | `/api/market/prices/forecast` | 48-hour forecast |

- **AC-111-1**: Consistent JSON envelope matching companion PRD pattern.

**FR-112: "Traditional stack vs lakehouse" comparison data**
The system shall expose a comparison endpoint `GET /api/comparison/traditional-vs-lakehouse` returning:

```json
{
  "data": {
    "scenario": "Hexham Turbine T-23 gearbox bearing overheat",
    "other": {
      "detection_resolution": "5 min",
      "detection_time_minutes": 47,
      "market_context": "none — no market data integration",
      "revenue_risk_visibility": "none — requires manual cross-reference",
      "time_to_new_asset_monitoring": "2–6 weeks",
      "licensing_model": "per-tag — cost scales with resolution",
      "data_format": "proprietary"
    },
    "lakehouse": {
      "detection_resolution": "1 sec",
      "detection_time_minutes": 8,
      "market_context": "integrated — NEM price forecast in same query",
      "revenue_risk_visibility": "$380,000 at risk in tomorrow's 4–6pm window",
      "time_to_new_asset_monitoring": "< 30 minutes",
      "licensing_model": "compute-based — resolution is free",
      "data_format": "open (Delta / Parquet)"
    },
    "improvement": {
      "detection_speed": "5.9x faster",
      "revenue_protected": "$380,000",
      "onboarding_speed": "168x faster"
    }
  }
}
```

- **AC-112-1**: Values are computed dynamically from actual demo data, not hardcoded (except traditional-side estimates).
- **AC-112-2**: The lakehouse detection time and revenue at risk come from real `health_scores` and `revenue_risk` tables.

---

### Phase 4 — Frontend: Revenue-at-Risk Monitor

**FR-113: App shell and navigation**
The system shall create a React app with the following pages:
- **Revenue Dashboard** (default landing)
- **Fleet Health**
- **Asset Risk Detail**
- **Price Forecast**
- **Traditional stack vs Lakehouse** (comparison)

- **AC-113-1**: Dark theme, control-room aesthetic (consistent with companion PRD).
- **AC-113-2**: Header shows: app name, active scenario, current NEM price, total fleet revenue at risk.

**FR-114: Revenue Dashboard page**
The main landing page, designed to make John say "I need this":

**Top bar — key numbers:**
- "Fleet Revenue at Risk (next 24h)" — big red/amber/green number (e.g., "$1.2M")
- "Assets at Risk" — count of assets with health < 0.8
- "Next High-Price Window" — time and forecast price
- "Current NEM Price" — live (well, 5-min delayed)

**Main area — two panels side by side:**

Left panel — **Revenue Risk Timeline**:
- X-axis: next 48 hours
- Y-axis (left): Forecast NEM price (area chart, with spikes highlighted in red)
- Y-axis (right): Fleet revenue at risk per hour (bar overlay)
- Clearly shows: "during tomorrow's 4–6pm spike, you have $800K at risk because 3 assets are degraded"

Right panel — **Assets Ranked by Risk**:
- Sorted table: Asset Name | Site | Type | Health Score | Revenue at Risk | Recommended Action
- Health score shown as colored pill (green/amber/red)
- Revenue at risk shown as dollar amount in bold
- Clicking a row navigates to Asset Risk Detail

- **AC-114-1**: Data refreshes every 10 seconds.
- **AC-114-2**: Revenue numbers formatted with $ and commas (e.g., "$1,234,567").
- **AC-114-3**: Price timeline clearly marks spike events with visual emphasis.

**FR-115: Fleet Health page**
Grid/card view of all assets (similar to companion PRD asset overview, but focused on health):
- Each card: Asset name, site, type icon, health score gauge (0–100%), primary risk tag if anomalous, revenue at risk
- Cards sorted by health score (worst first)
- Filter by: site, asset type, risk level (critical/warning/healthy)

- **AC-115-1**: Health gauge uses gradient: green (>80%) → amber (50–80%) → red (<50%).
- **AC-115-2**: Cards with revenue at risk > $50K have a pulsing border highlight.

**FR-116: Asset Risk Detail page**
For a single asset, shows:

**Header**: Asset name, site, type, capacity, health score, revenue at risk

**Section 1 — Why this asset is at risk:**
- List of anomalous tags with current value, expected range, z-score
- "Primary risk: nacelle/temperature_c at 87°C (expected 62–74°C, z-score: 3.2)"
- Detection speed comparison card (FR-108): "Detected in 8 min at 1-sec resolution. Would take 47 min at 5-min resolution."

**Section 2 — Revenue impact:**
- Timeline showing forecast prices for next 48h
- Highlighted window where this asset's revenue is at risk
- Dollar amount: "If this asset trips during the 4–6pm window tomorrow: **$380,000 lost revenue**"

**Section 3 — Key tag trends:**
- 4–6 trend charts for the asset's key tags (same as companion PRD)
- Anomalous tags highlighted with red threshold bands

**Section 4 — Recommended action:**
- Big card with the recommended action and urgency level

- **AC-116-1**: All data from APIs defined in FR-107, FR-111.
- **AC-116-2**: Detection comparison prominently displayed (traditional vs lakehouse).

**FR-117: Price Forecast page**
- 48-hour NEM price forecast chart (line + area for spike events)
- Overlay: fleet availability forecast (what % of fleet is healthy enough to capture the spike)
- Table of upcoming spike events with: time, forecast price, fleet MW at risk, revenue at risk

- **AC-117-1**: Spike events defined as intervals where forecast > $300/MWh.
- **AC-117-2**: Each spike event row is clickable → shows which specific assets are at risk.

**FR-118: Traditional stack vs Lakehouse comparison page**
Designed as the "leave-behind" that John shows his leadership:

**Side-by-side comparison table** (rendered from FR-112 API data):
- Two columns: Other platforms | Databricks Lakehouse
- Rows populated dynamically from the live demo data

**Live example callout:**
- "Right now in this demo, Turbine T-23 at Hexham has a gearbox bearing anomaly."
- "At 5-min resolution, detection would take ~47 minutes. We detected it in 8 minutes."
- "Traditional stacks often cannot tell you this matters because tomorrow's price hits $8,000/MWh."
- "We can. Revenue at risk: $380,000."

**Cost model comparison:**
- Other platforms: Per-tag licensing × 2M tags × higher resolution = exponential cost
- Databricks: Compute-based pricing × SDT compression = flat cost regardless of resolution

- **AC-118-1**: Live data populates the comparison dynamically.
- **AC-118-2**: Design is clean enough to screenshot for a follow-up email.

**FR-119: Degradation injection UI**
For the presenter to trigger scenarios during the demo:
- Dropdown: select an asset
- Dropdown: select scenario (gearbox overheat / thermal runaway / inverter drop)
- Slider: duration (5–60 minutes)
- "Inject" button → calls `POST /api/scenarios/inject`
- Status indicator showing active scenarios

- **AC-119-1**: Accessible from a "Demo Controls" button in the nav (subtle, not customer-facing).
- **AC-119-2**: After injection, health score and revenue risk update within 2 minutes.

**FR-120: Notification/alert banner**
When a new high-risk event is detected (asset health drops below 0.5 while a price spike is forecast):
- A banner slides down from the top: "⚠️ ALERT: Hexham T-23 health critical (0.32) — $380K revenue at risk in tomorrow's 4–6pm spike. Action: Schedule maintenance tonight."
- Banner persists until dismissed or health recovers.

- **AC-120-1**: Alert triggers automatically based on polling data.
- **AC-120-2**: Alert includes direct link to the Asset Risk Detail page.

**FR-121: Responsive layout**
- Optimized for 1920x1080 projector (primary demo target)
- Two-column layout collapses to single on smaller screens

- **AC-121-1**: No horizontal scroll at 1920x1080.
- **AC-121-2**: All charts and tables are readable from 3 meters away (projector distance).

---

### Phase 5 — Databricks App packaging and demo readiness

**FR-122: Databricks App configuration**
The system shall include an `app.yaml` for Databricks Apps deployment:
```yaml
command: ['uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', '$DATABRICKS_APP_PORT']
env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom: sql-warehouse
  - name: DATABRICKS_CATALOG
    value: 'agl_demo'
  - name: DATABRICKS_SCHEMA
    value: 'ot'
  - name: STATIC_DIR
    value: './static'
```

- **AC-122-1**: `app.yaml` is valid and follows Databricks Apps spec.
- **AC-122-2**: App can be deployed via `databricks apps deploy` CLI or Databricks Asset Bundles.

**FR-123: Unified build**
The system shall produce a single deployable artifact:
- React frontend built to static files (`npm run build` in frontend/)
- FastAPI server serves both the API and the static frontend from `./static`
- Single `uvicorn backend.main:app` entry point

- **AC-123-1**: Frontend build copies to `demo/app/static/`, then `uvicorn backend.main:app` serves the full app.
- **AC-123-2**: No separate frontend dev server needed in production mode.

**FR-124: Demo seed script**
A single script that seeds all demo data:
1. Creates tables (FR-100)
2. Loads AEMO price data (FR-101)
3. Generates price forecast (FR-102)
4. Populates assets (FR-103)
5. Injects one degradation scenario (FR-106)

- **AC-124-1**: `python -m scripts.seed_demo` or equivalent runs all steps.
- **AC-124-2**: Idempotent — safe to re-run.

**FR-125: README with demo walkthrough**
- Prerequisites and setup
- Architecture diagram (Mermaid)
- Step-by-step demo script matching the narrative in Section 5
- Screenshots placeholder

- **AC-125-1**: README is comprehensive enough for another SA to run the demo independently.

**FR-126: Companion PRD integration**
The app must work alongside the Zerobus ingest demo (companion PRD):
- Shares the same `agl_demo` catalog and `ot` schema for tag data
- Can run as a separate Databricks App or be merged into the companion frontend

- **AC-126-1**: App reads from `agl_demo.ot.raw_tags` (written by Zerobus).
- **AC-126-2**: If companion simulator is not running, app gracefully shows "No live data — using historical" with the seeded data.

---

## 5 · Demo narrative

### The 10-minute pitch to John (for presenter reference)

1. **Open** (1 min):
   "John, you told us the lakehouse can standardize your technologies. We agree. But let me show you something traditional historians typically cannot do — answer the question that actually drives your P&L."

2. **Revenue Dashboard** (2 min):
   Show the landing page. "$1.2M fleet revenue at risk in the next 24 hours." Point to the price forecast timeline. "See that spike tomorrow at 4pm? $8,000/MWh. Three of your assets have health issues."

3. **Drill into the worst asset** (3 min):
   Click Hexham T-23. Show the gearbox temperature drifting. Show the z-score. Show the detection comparison: "8 minutes to detect at 1-second resolution. 47 minutes at 5-minute resolution." Show the revenue number: "$380,000 at risk."

4. **The question traditional stacks can't answer** (2 min):
   "In a process historian UI, you'd see the temperature trend. But would you know that tomorrow's price is $8,000? Would you know the revenue impact? Would you prioritize this turbine over the one in Broken Hill where tomorrow's price is $50? No. Because the historian doesn't know about the market."

5. **Comparison page** (1 min):
   Show the side-by-side. "Same compression algorithm. Faster detection. Market-aware risk scoring. Open format. No per-tag licensing scaling problem."

6. **Close** (1 min):
   "You have 2GW+ of new wind coming. Liddell and Tomago batteries coming online. Every week those assets operate without this kind of monitoring is a week where a $300K price spike can catch you blind. With Zerobus and the lakehouse, they're monitored from day one."

---

## 6 · Non-functional requirements

**NFR-100: Query performance**
All API endpoints must respond in < 3 seconds under demo load.

**NFR-101: Databricks Apps compatible**
Must deploy as a Databricks App — single container, serverless, no external infra.

**NFR-102: No real AGL financial data**
All revenue figures are computed from synthetic health scores and publicly available AEMO prices.

**NFR-103: Presentation quality**
UI must be polished enough to show to a C-level stakeholder. No placeholder text, no "lorem ipsum", no broken layouts.

**NFR-104: Graceful without live ingest**
If the Zerobus simulator is not actively running, the app must still function using the last available data plus the seeded historical data.

---

## 7 · Loop instructions for Claude Code

1. Read this entire PRD before writing any code.
2. This app depends on the companion `PRD.md` for OT tag data. Assume those tables exist.
3. Implement phases in order (Phase 1 → 2 → 3 → 4 → 5).
4. After completing each phase, verify all `AC-*` criteria for that phase.
5. The revenue-at-risk calculation (FR-109) and the comparison (FR-112, FR-118) are the two most important features — they are why this app exists.
6. Write clean, production-quality code — this will be shown to a customer executive.
7. Do NOT skip acceptance criteria. Each one matters.
8. When all `FR-*` and `NFR-*` are implemented and all `AC-*` pass: output `<promise>DONE</promise>`.
