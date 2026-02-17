# Generic Zerobus Metrics App (Optional)

This is a minimal, generic Databricks App scaffold for visualizing connector metrics.

It is intentionally outside the connector core runtime and is **not required** for module functionality.

## What it includes

- FastAPI backend (`backend/`)
- Simple dashboard page (`frontend/`)
- Generic metrics endpoints:
  - `GET /api/health`
  - `GET /api/metrics/throughput?minutes=15`
  - `GET /api/metrics/latency?minutes=15`
  - `GET /api/metrics/compression?minutes=15`

## Environment variables

- `DATABRICKS_HOST` (required)
- `DATABRICKS_WAREHOUSE_ID` (required)
- Auth (one of):
  - `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`
  - `DATABRICKS_TOKEN`
- `APP_TARGET_CATALOG` (default: `main`)
- `APP_TARGET_SCHEMA` (default: `default`)
- `APP_TARGET_TABLE` (default: `raw_tags`)
- `STATIC_DIR` (default: `./frontend`)
- `PORT` (default: `8000`)

## Local run

```bash
cd tools/optional_apps/generic_metrics_app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open: `http://localhost:8000`

## Databricks App command

Use `app.yaml`:

```yaml
command: ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "$DATABRICKS_APP_PORT"]
```

