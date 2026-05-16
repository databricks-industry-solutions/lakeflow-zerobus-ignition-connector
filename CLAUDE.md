# CLAUDE.md

This file provides guidance for working in this repository.

## Project scope

This repository is centered on the Ignition OT ingestion module:

- `module/` for source code
- `releases/` for built `.modl` artifacts
- `DEPLOYMENT.md` for installation and runtime configuration

The module supports two exclusive sinks:

- `sinkMode=zerobus` -> Zerobus ingest to Delta
- `sinkMode=lakebase` -> PostgreSQL sink to Lakebase

## Build and test

Run from repository root:

```bash
make build-83
make build-81
```

Run Java tests from `module/` with local Ignition SDK jars:

```bash
cd module
./gradlew test -PignitionHome=/usr/local/ignition -PbuildForIgnitionVersion=8.3.2
./gradlew test -PignitionHome=/usr/local/ignition8.1 -PbuildForIgnitionVersion=8.1.50
```

## Local runtime (Docker)

```bash
make up-83
make logs-83
```

After first-time setup wizard completion:

```bash
make configure-83
make health-83
make diag-83
```

Sink switching examples:

```bash
make configure-zerobus-83
make configure-lakebase-83
```

Use equivalent `*-81` targets for Ignition 8.1.

## Core module flow

1. Event intake (direct subscriptions or HTTP ingest)
2. `TagEvent` normalization
3. `OTEvent` mapping
4. buffer/store-and-forward
5. sink delivery (`zerobus` or `lakebase`)

HTTP ingest endpoints:

- `POST /system/zerobus/ingest`
- `POST /system/zerobus/ingest/batch`

## Important paths

- `module/src/main/java/com/example/ignition/zerobus/`
- `module/src/main/proto/ot_event.proto`
- `docker/ignition-gateway/`
- `DEPLOYMENT.md`
