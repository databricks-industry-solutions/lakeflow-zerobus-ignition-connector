# Task: Phase 6 - Deploy to Databricks Apps with git integration

## Objective

Restructure the project for Databricks Apps deployment using git integration (NOT DABs/Asset Bundles). The Node.js app (backend + frontend) must be deployable as a single Databricks App, with `app.yaml` and `package.json` at the same directory level. Configure resources (SQL warehouse, secrets) in `app.yaml` using the Databricks Apps resource model. The simulator runs separately (not part of the deployed app).

## Context

Read these files to understand the current state:
- `PRD.md` - Full product requirements
- `CLAUDE.md` - Project conventions
- `frontend/` - React frontend (Vite + Tailwind)
- `backend/` - Express API server
- `simulator/` - Tag simulator (runs separately, not deployed as app)
- `progress.txt` - Learnings from previous iterations (READ THIS FIRST)

Check what Phases 1-5 built:
```bash
git log --oneline -30
ls -la frontend/ backend/ simulator/
```

## Technical constraints

- **Deployment method**: Git integration (NOT Databricks Asset Bundles). The app deploys by pointing Databricks Apps at this git repo + branch.
- **app.yaml + package.json must be co-located**: Databricks Apps expects `package.json` at the same level as `app.yaml`. The build process runs `npm install` then `npm run build` then `npm run start` from that directory.
- **Single deployable unit**: The frontend must be built as static assets and served by the backend Express server. In production mode, Express serves the Vite build output.
- **Port**: The app MUST listen on `process.env.PORT` (Databricks assigns this dynamically). Do NOT hardcode a port.
- **Authentication**: Databricks Apps automatically provides `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, and `DATABRICKS_HOST` as environment variables to the app's service principal. Use these instead of PAT tokens.
- **Resources**: SQL warehouse and secrets are declared as app resources and injected via `app.yaml` env vars using `valueFrom`.
- **Do NOT use DABs**: No `databricks.yml`, no bundle deploy. Git integration only.
- **Do NOT break existing gates**: All Phase 1-5 tests must continue to pass.
- **Simulator is separate**: The simulator is NOT part of the Databricks App. It runs on-prem or locally, pushing data through Zerobus. Only the backend + frontend are deployed.

## Requirements

### FR-029: Unified build for Databricks Apps
Restructure so the app can be built and served from a single directory.

**Option A (preferred)**: Create an `app/` directory at repo root with its own `package.json` that:
- Has a `build` script that builds the frontend (Vite) and copies output to a `static/` directory
- Has a `start` script that runs the backend Express server which serves both API routes and static frontend files
- Dependencies include both backend and frontend production deps

**Option B**: Use a root-level package.json with workspace-style build.

Acceptance criteria:
- `app.yaml` exists at the app directory root
- `package.json` exists at the same level as `app.yaml`
- `npm install` installs all dependencies
- `npm run build` builds the frontend into static assets
- `npm run start` starts Express serving both API and static frontend
- Express serves frontend static files at `/` and API at `/api/*`
- App listens on `process.env.PORT` (not hardcoded)

### FR-030: app.yaml configuration
Create `app.yaml` with proper resource references:

```yaml
command: ['npm', 'run', 'start']
env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom: sql-warehouse
  - name: DATABRICKS_CATALOG
    value: 'agl_demo'
  - name: DATABRICKS_SCHEMA
    value: 'ot'
  - name: NODE_ENV
    value: 'production'
```

Acceptance criteria:
- `app.yaml` exists with `command` and `env` sections
- SQL warehouse referenced via `valueFrom: sql-warehouse`
- Non-secret config values set directly (catalog, schema, NODE_ENV)
- No secrets hardcoded in app.yaml

### FR-031: Backend serves frontend static assets
In production mode (`NODE_ENV=production`), Express serves the built frontend:
- Static files from the build output directory
- SPA fallback: any non-API route returns `index.html` (for client-side routing)
- API routes at `/api/*` take precedence over static files

Acceptance criteria:
- `GET /` returns the frontend HTML in production mode
- `GET /api/health` still returns JSON health check
- Client-side routes (e.g., `/assets/123`) return index.html (not 404)
- Static assets (JS, CSS, images) are served with correct MIME types

### FR-032: Databricks authentication via service principal
Use the auto-injected service principal credentials for Databricks SQL queries instead of PAT tokens.

Acceptance criteria:
- Backend reads `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` from env
- Falls back to `DATABRICKS_TOKEN` (PAT) for local development
- `@databricks/sql` connection uses OAuth M2M when client ID/secret are present
- Config validation accepts either (CLIENT_ID + CLIENT_SECRET) or TOKEN

### FR-033: Deployment documentation
Document the git integration deployment process.

Acceptance criteria:
- README section: "Deploying to Databricks Apps"
- Steps: create app in workspace, configure git repo URL, add resources (SQL warehouse), deploy from branch
- Example CLI commands using `databricks apps create` and `databricks apps deploy`
- Troubleshooting: common issues (port binding, missing resources, auth failures)

## Test plan (write these FIRST)

### Backend tests (`backend/src/__tests__/` or `app/src/__tests__/`)

- [ ] `config.test.ts`: Config accepts DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET as valid auth (no TOKEN needed)
- [ ] `config.test.ts`: Config accepts DATABRICKS_TOKEN as fallback auth for local dev
- [ ] `config.test.ts`: Config rejects missing auth entirely (no CLIENT_ID, no TOKEN)
- [ ] `config.test.ts`: Config reads DATABRICKS_WAREHOUSE_ID from env (used by app.yaml valueFrom)
- [ ] `static-serve.test.ts`: In production mode, GET / returns HTML content-type
- [ ] `static-serve.test.ts`: In production mode, GET /api/health still returns JSON
- [ ] `static-serve.test.ts`: In production mode, GET /nonexistent-route returns HTML (SPA fallback)
- [ ] `static-serve.test.ts`: API routes take precedence over static file serving

### Configuration validation tests

- [ ] `app-yaml.test.ts`: app.yaml exists and is valid YAML
- [ ] `app-yaml.test.ts`: app.yaml has `command` field
- [ ] `app-yaml.test.ts`: app.yaml has env entries with `valueFrom: sql-warehouse`
- [ ] `app-yaml.test.ts`: app.yaml does NOT contain any hardcoded secrets or tokens
- [ ] `package-json.test.ts`: package.json exists at same level as app.yaml
- [ ] `package-json.test.ts`: package.json has `build` and `start` scripts
- [ ] `readme.test.ts`: README.md contains "Deploying to Databricks Apps" section

## Gates

Run `bash gates.sh` to verify. Same 13 gates as previous phases.

| Gate | Command |
|------|---------|
| FE Install | `npm --prefix frontend install --silent` |
| BE Install | `npm --prefix backend install --silent` |
| Sim Install | `npm --prefix simulator install --silent` |
| FE Lint | `npm --prefix frontend run lint` |
| BE Lint | `npm --prefix backend run lint` |
| Sim Lint | `npm --prefix simulator run lint` |
| FE Typecheck | `npm --prefix frontend run typecheck` |
| BE Typecheck | `npm --prefix backend run typecheck` |
| Sim Typecheck | `npm --prefix simulator run typecheck` |
| FE Tests | `npm --prefix frontend run test -- --run` |
| BE Tests | `npm --prefix backend run test -- --run` |
| Sim Tests | `npm --prefix simulator run test -- --run` |
| FE Build | `npm --prefix frontend run build` |

**Note**: If you restructure into an `app/` directory, you may need to update `gates.sh` to also validate the app build. Add gates as needed but do NOT remove existing ones.

## Completion criteria

The task is COMPLETE only when ALL of the following are true:

1. You have run `bash gates.sh` and the output shows **all gates passed, 0 failed**
2. The exit code of `bash gates.sh` is **0**
3. All 15 tests from the test plan above exist as real test files and are passing
4. `app.yaml` exists and is valid with command, env, and sql-warehouse resource reference
5. `package.json` exists at the same level as `app.yaml` with build and start scripts
6. Express serves static frontend assets in production mode with SPA fallback
7. Backend supports both service principal auth (CLIENT_ID + CLIENT_SECRET) and PAT token fallback
8. README.md includes Databricks Apps deployment section
9. All Phase 1-5 tests still pass

**You MUST verify completion mechanically.** Do NOT self-assess. Run `bash gates.sh` and read the output.

## Instructions

Follow TDD (red-green-refactor):

1. Read context files, especially `progress.txt`
2. Plan the restructuring: decide on Option A (app/ directory) vs Option B (root package.json)
3. **Red**: Write config tests for service principal auth
4. **Green**: Update config to support CLIENT_ID + CLIENT_SECRET and DATABRICKS_WAREHOUSE_ID
5. **Red**: Write static serving tests
6. **Green**: Add Express static file serving and SPA fallback for production mode
7. Create `app.yaml` with proper resource references
8. Ensure `package.json` is co-located with `app.yaml`
9. Add build script that produces frontend static assets
10. Write app.yaml and package.json validation tests
11. Update README.md with deployment documentation
12. Update `gates.sh` if needed to cover the new app build
13. Run `bash gates.sh` - all gates should pass
14. Commit and update `progress.txt`

## Signaling completion

When you are done, you MUST follow this exact sequence:

1. Run `bash gates.sh`
2. Read the output. Confirm all gates pass with 0 failures.
3. If ANY gate shows `FAIL`, do NOT proceed - fix the issue and re-run.
4. Only after confirming all gates pass, output this EXACT string on its own line:

<promise>TASK COMPLETE</promise>

### Rules about the completion signal

- You MUST run `bash gates.sh` immediately before outputting the promise. Not 5 steps before. Immediately before.
- You MUST see all gates passed, 0 failed in the output. If you see anything else, you are NOT done.
- Do NOT output `<promise>TASK COMPLETE</promise>` if even a single gate failed.
- Do NOT output the promise based on your own judgment, memory, or belief that things work. Only the gate output matters.
- Do NOT guess, assume, or predict that gates will pass. Run them and read the result.
- Do NOT output the promise to "try to finish" or "move on". It means "all work is verified done".
- If you are stuck and cannot make all gates pass after sustained effort, do NOT output the promise. Instead, append your blockers and what you tried to `progress.txt` so the next iteration can pick up where you left off.
