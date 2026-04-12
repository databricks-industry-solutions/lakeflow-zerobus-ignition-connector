# AGL analytics (agl_analytics)

Python package for AGL OT Lakehouse analytics: health scoring, revenue-at-risk, market data.

## Deploy pipeline (SDK, Git folder in workspace)

The pipeline is **not** in the Databricks Asset Bundle. Create or update it with the SDK so it points at a **Git folder (Repos)** in the workspace. No wheel build or bundle artifact.

1. **Clone the repo in the workspace** (Repos) or ensure the code is at a workspace path.
2. **Run setup SQL** once (catalog, schema, volume, SP grants):  
   `DATABRICKS_CONFIG_PROFILE=daveok uv run --with databricks-sdk python onboarding/databricks/run_setup_sql.py`
3. **Create/update the pipeline** with the SDK. Use either the workspace path or the folder object ID from the browse URL:

   ```bash
   # By path (e.g. Repos or Users folder)
   DATABRICKS_CONFIG_PROFILE=daveok uv run --with databricks-sdk python onboarding/databricks/deploy_pipeline_sdk.py \
     --repo-path /Repos/<your-user>@databricks.com/lakeflow-ignition-zerobus-connector

   # By folder ID (from .../browse/folders/<id> in the workspace UI)
   DATABRICKS_CONFIG_PROFILE=daveok uv run --with databricks-sdk python onboarding/databricks/deploy_pipeline_sdk.py \
     --folder-id 805036456196513
   ```

   Pipeline `root_path` = `<repo-path>/pipelines/sdp`; libraries = `transformations/**`; environment uses `-e <root_path>` so `agl_analytics` is importable from the repo.
4. **Run the pipeline** from the UI or:  
   `databricks pipelines start-update --pipeline-id <id>`

Optional env (same as `run_setup_sql.py`): `CATALOG`, `SCHEMA`, `PIPELINE_NAME` (default `[production] agl-etl`).

## Health scores ML model

The `health_scores` materialized view uses a Unity Catalog–registered **IsolationForest** model for anomaly-based health scoring, blended with a z-score baseline.

- **Model**: `agl_demo.ot.asset_health_model` (or `{catalog}.{schema}.asset_health_model`).
- **Training**: Run `train_health_model.py` once (or on a schedule) as a Databricks job or notebook. It trains on synthetic normal-operations data and registers a new version to UC. From the repo root: `make db-train-health-model` (or `onboarding/databricks/create_train_health_model_job.py --repo-path <workspace-repo-path>`) creates/updates a job that runs the script from the workspace repo and waits until the run succeeds.
- **Version**: The pipeline uses a configurable version (default `4`) via the pipeline configuration key `health_model_version`. Set it in pipeline settings if you promote a new version.
- **Fallback**: If the model is missing or fails to load, `health_scores` still computes; `ml_health` will be null and only the z-score component is used. Ensure at least one model version exists (and matches the configured version) so that `ml_health` is populated.
- **Verification**: After a pipeline run, run `make db-verify-ml` (or `DATABRICKS_CONFIG_PROFILE=daveok uv run --with databricks-sdk python onboarding/databricks/verify_ml_health.py`) to query `health_scores` and confirm the ML path is active (non-null `ml_health`). The SQL is in `pipelines/sdp/verify_health_scores.sql`.

## Build (optional)

```bash
uv build pipelines/sdp
```

Produces `dist/agl_analytics-0.1.0-py3-none-any.whl`. Only needed if you use a wheel-based pipeline config instead of the SDK Git-folder flow above.
