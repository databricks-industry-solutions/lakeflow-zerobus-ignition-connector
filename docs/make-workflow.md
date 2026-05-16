# Makefile workflow (module-focused)

Use Make targets from the repository root to build and operate the Ignition ingestion module runtime.

## Build module artifacts

```bash
make build-83
make build-81
```

These produce version-specific `.modl` artifacts under `releases/`.

## Run local Ignition gateway (Docker)

```bash
make up-83
make logs-83
```

If this is a fresh gateway volume, complete the setup wizard, then configure the module.

## Configure connector

```bash
make configure-83
make health-83
make diag-83
```

Sink mode switch commands:

```bash
make configure-zerobus-83
make configure-lakebase-83
```

Use equivalent `*-81` targets for Ignition 8.1.

## Discover all available targets

```bash
make help
```

