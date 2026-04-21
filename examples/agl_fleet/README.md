# AGL Fleet Simulator

Direct synthetic data generator that sends BESS, Grid, Market, and CMMS tag events to an Ignition 8.3 Gateway via the Zerobus HTTP ingest endpoint. No Kafka or middleware required.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker + Colima (or Docker Desktop) for the Ignition Gateway
- The Zerobus `.modl` file at `releases/zerobus-connector-1.0.10-ignition-8.3.modl`

## Step 1 - Start the Ignition 8.3 Gateway

```bash
cd docker/ignition-gateway
docker compose -f docker-compose.83.yml up -d
```

This starts Ignition 8.3.2 on `http://localhost:7088` with the Zerobus module auto-loaded. First boot takes ~60s to initialise.

Wait for the container to be healthy:

```bash
docker ps --filter name=ignition83_7088 --format '{{.Status}}'
# Should show: Up ... (healthy)
```

## Step 2 - Complete Ignition first-time setup

Open `http://localhost:7088` in a browser and complete the setup wizard:

1. Accept the EULA
2. Create an admin user (e.g. `admin` / `password`)
3. Skip edition selection (trial is fine)
4. Finish setup

The Zerobus module will appear under **Config > Modules** automatically.

## Step 3 - Configure the Zerobus module

The module needs Databricks connection details to stream events into a Delta table.

### Option A - Automated setup from Databricks CLI profile (recommended)

This reads OAuth M2M credentials from a `~/.databrickscfg` profile and pushes them to the Gateway:

```bash
cd examples/agl_fleet

# One-shot: configure Gateway + start simulator
uv run --extra setup agl-sim --setup \
    --profile agl-demo \
    --zerobus-endpoint 7405607216190670.zerobus.eastus2.azuredatabricks.net

# Or configure only (no simulation)
uv run --extra setup agl-sim --setup-only \
    --profile agl-demo \
    --zerobus-endpoint 7405607216190670.zerobus.eastus2.azuredatabricks.net
```

The Databricks CLI profile must have `client_id` and `client_secret` set (OAuth M2M auth). Example `~/.databrickscfg` entry:

```ini
[agl-demo]
host          = https://adb-7405607216190670.10.azuredatabricks.net
client_id     = 66c066ad-d5a9-496f-8da5-6d7bc2f5d954
client_secret = <your-client-secret>
auth_type     = oauth-m2m
```

### Option B - Manual curl

```bash
# View current config
curl -s http://localhost:7088/system/zerobus/config | python3 -m json.tool

# Push correct config
curl -s -X POST http://localhost:7088/system/zerobus/config \
  -H 'Content-Type: application/json' \
  -d '{
    "workspaceUrl": "https://adb-7405607216190670.10.azuredatabricks.net",
    "zerobusEndpoint": "7405607216190670.zerobus.eastus2.azuredatabricks.net",
    "oauthClientId": "66c066ad-d5a9-496f-8da5-6d7bc2f5d954",
    "oauthClientSecret": "<secret>",
    "targetTable": "agl_demo.ot.raw_tags",
    "enableDirectSubscriptions": false,
    "enabled": true
  }'
```

### Zerobus endpoint format

The endpoint follows the pattern `<workspace-id>.zerobus.<region>.<cloud-domain>`:

| Cloud | Format | Example |
|-------|--------|---------|
| Azure | `<workspace-id>.zerobus.<region>.azuredatabricks.net` | `7405607216190670.zerobus.eastus2.azuredatabricks.net` |
| AWS   | `<workspace-id>.zerobus.<region>.cloud.databricks.com` | `1234567890123456.zerobus.us-west-2.cloud.databricks.com` |

The workspace ID is the numeric part from your workspace URL (e.g. `adb-7405607216190670` → `7405607216190670`).

### Current working config (daveok workspace)

| Setting | Value |
|---------|-------|
| Workspace URL | `https://adb-7405607216190670.10.azuredatabricks.net` |
| Zerobus Endpoint | `7405607216190670.zerobus.eastus2.azuredatabricks.net` |
| Service Principal | `66c066ad-d5a9-496f-8da5-6d7bc2f5d954` |
| Target Table | `agl_demo.ot.raw_tags` |
| Region | `eastus2` |

### Troubleshooting

If you see `Failed to get Zerobus token` in diagnostics, check:

1. **Workspace URL and endpoint must match** — both must point to the same workspace ID
2. **SP must have UC permissions** — `USE CATALOG`, `USE SCHEMA`, `MODIFY` + `SELECT` on the target table
3. **Endpoint region must match the workspace region** — use the account API or Azure portal to verify
4. **The target table schema must exist** — `agl_demo.ot` not `agl_demo.bronze`

Verify with:

```bash
# Check diagnostics (look for Connected: true)
curl -s http://localhost:7088/system/zerobus/diagnostics

# Quick connectivity test with the Python SDK (bypasses Ignition)
cd zerobus-test && uv run python test_zerobus.py
```

## Step 4 - Install dependencies and run the simulator

```bash
cd examples/agl_fleet
uv sync
```

### Basic run - single site, single unit

```bash
uv run agl-sim --gateway http://localhost:7088
```

### Run for a fixed number of ticks (e.g. 10)

```bash
uv run agl-sim --gateway http://localhost:7088 --ticks 10
```

### Multi-site scaling - 3 sites, 4 BESS units each

```bash
uv run agl-sim --gateway http://localhost:7088 --sites 3 --units 4
```

### Dry run - generate events without sending

```bash
uv run agl-sim --dry-run --ticks 5
```

### Using environment variables

```bash
IGNITION_GATEWAY_URL=http://localhost:7088 \
SIM_INTERVAL_MS=500 \
SIM_SITES=2 \
SIM_UNITS=3 \
uv run agl-sim
```

## Expected output

```
=== AGL Fleet Simulator (Direct HTTP Ingest) ===
  Gateway:        http://localhost:7088
  Sites:          1 (Tomago (NSW))
  BESS units:     1/site (1 total)
  Events/tick:    ~39 (BESS+Grid, excl. market/cmms)
  ...
  Gateway status: ok
  Gateway config: already sufficient (>=58 eps, >=10000 queue)

[sim] Starting simulation... (Ctrl+C to stop)

[tick 1] sent=48 accepted=48 dropped=0
[tick 2] sent=39 accepted=39 dropped=0
[tick 3] sent=43 accepted=43 dropped=0
```

All events should show `dropped=0`. If you see drops, the module may not be enabled or configured.

## Verification

Check the health endpoint:

```bash
curl -s http://localhost:7088/system/zerobus/health
# {"status":"ok","enabled":true}
```

Check diagnostics for event counts:

```bash
curl -s http://localhost:7088/system/zerobus/diagnostics | python3 -m json.tool
```

## CLI reference

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--gateway` | `IGNITION_GATEWAY_URL` | `http://localhost:7088` | Gateway URL |
| `--api-key` | `ZEROBUS_API_KEY` | none | Optional ingest API key |
| `--interval` | `SIM_INTERVAL_MS` | `1000` | Tick interval (ms) |
| `--ticks` | `SIM_TICKS` | `0` (infinite) | Number of ticks |
| `--sites` | `SIM_SITES` | `1` | Number of sites (1-5) |
| `--units` | `SIM_UNITS` | `1` | BESS units per site (1-8) |
| `--market-interval` | - | `2000` | Market tick interval (ms) |
| `--cmms-interval` | - | `10000` | CMMS tick interval (ms) |
| `--dry-run` | - | `false` | Generate without sending |

## Site topology

| Index | State | Location |
|-------|-------|----------|
| 1 | NSW | Tomago |
| 2 | NSW | Liddell |
| 3 | NSW | BrokenHill |
| 4 | QLD | Callide |
| 5 | QLD | Gladstone |

## Events per tick (single site, single unit)

| Generator | Events | Interval |
|-----------|--------|----------|
| BESS | 23 | Every tick |
| Grid | 16 | Every tick |
| Market | 4 | Every 2s |
| CMMS | 5 | Every 10s |

## Teardown

```bash
# Stop the simulator
Ctrl+C

# Stop the Gateway
cd docker/ignition-gateway
docker compose -f docker-compose.83.yml down

# Remove volumes too (full reset)
docker compose -f docker-compose.83.yml down -v
```
