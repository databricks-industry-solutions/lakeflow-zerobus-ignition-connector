# Makefile workflow (Ignition 8.3 + Databricks)

This project’s recommended path for a **full** demo—service principal, Unity Catalog objects, Databricks Asset Bundle deploy, Ignition 8.3 gateway in Docker, and synthetic tag traffic—is the **Makefile at the repo root**.

Developer-oriented tables and pitfall notes live in [CLAUDE.md](../CLAUDE.md). This page is a short runbook for “run it again” scenarios.

## Environment

Optional overrides live in `.env` (copy from [.env.example](../.env.example)):

```bash
set -a && source .env && set +a
```

Then run `make` targets from the **repository root**.

## First-time end-to-end (8.3)

Automated steps 1–4:

```bash
make bootstrap-83
```

When that finishes, run the manual gateway steps in order:

```bash
make setup-wizard-83    # Browser: EULA, admin user, trial
make configure-83       # Push SP + Zerobus config to the gateway
make simulate-83        # Start synthetic tag events (AGL Fleet Simulator)
make links-83           # Print workspace / app / gateway URLs
```

Optional ML training job:

```bash
make db-train-health-model
```

## Run it again (common cases)

| Situation | Typical commands |
|-----------|------------------|
| Gateway already set up; you just want fresh simulator traffic | `make simulate-83` |
| You want URLs again | `make links-83` |
| You recreated the container volume (fresh Ignition) | `make setup-wizard-83` → `make configure-83` → `make simulate-83` → `make links-83` |
| You changed Databricks/workspace and need the full stack rebuilt from Makefile | `make bootstrap-83` then the manual steps above |

## Full reset (Databricks resources + gateway)

```bash
make db-clean clean-83 bootstrap-83
```

Then complete the manual block again: `setup-wizard-83`, `configure-83`, `simulate-83`, `links-83`.

## Discover targets

```bash
make help
```

Lists build, gateway, configure, Databricks, Lakebase, simulator, and training targets.

## Ignition 8.1

Parallel artifacts use `*-81` targets (e.g. `make build-81`, `make up-81`). The 8.3 flow above is the primary demo path documented in the Makefile help text.
