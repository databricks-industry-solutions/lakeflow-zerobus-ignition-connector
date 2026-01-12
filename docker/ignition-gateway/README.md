## Ignition Gateway in Docker (Colima on macOS)

This repo already supports **Docker-based `.modl` builds** via `docker/Dockerfile.build-modl`.
This document covers running a full **Ignition Gateway** in Docker (useful for demos without installing Ignition on your laptop).

### Requirements (macOS)

- **Colima** installed (`brew install colima`)
- **Docker CLI** installed (`brew install docker`)
- Colima started and Docker context set:

```bash
colima start --arch aarch64
docker context use colima
docker version
```

If Colima fails with `permission denied` creating `~/.docker/contexts`, fix ownership:

```bash
sudo chown -R "$(whoami)":"$(id -gn)" ~/.docker
chmod 700 ~/.docker
```

### Ports

The Ignition container listens on:
- **HTTP**: 8088
- **HTTPS**: 8043

We typically map those to non-conflicting host ports, e.g.:
- `8097 -> 8088`
- `8047 -> 8043`

### Persistent state (projects/users/modules)

Ignition persists its state under the container path:
- `/usr/local/bin/ignition/data`

Use a **Docker named volume** so restarts keep:
- projects
- tag providers + tags
- installed modules
- internal config DB (users/roles, etc.)

### How credentials are handled

In the official `inductiveautomation/ignition` image:
- The entrypoint seeds the data directory if empty.
- When the data volume is **new/empty**, Ignition requires initial commissioning via the web UI at `/Start`.
- Once commissioned, users/roles are stored in the **gateway internal config DB** inside the persisted `data` volume.

So: **you do not recreate credentials on restart** as long as you reuse the same data volume.

### Recommended: bootstrap from an existing working gateway (.gwbk restore)

Instead of commissioning manually, export a `.gwbk` from an existing gateway and restore it into Docker.

#### 1) Create a `.gwbk` from a local Ignition install (non-GUI)

From a macOS Ignition zip install (example path):

```bash
/usr/local/ignition81/gwcmd.sh -i
mkdir -p ~/colima/gwbk
/usr/local/ignition81/gwcmd.sh -b ~/colima/gwbk/ignition81.gwbk -z 900 -y
```

#### 2) Run Ignition in Docker and restore the `.gwbk`

Important:
- Restore into a **fresh** data volume (don’t restore into an already-initialized gateway volume).
- Pass JVM args after `--` so the entrypoint doesn’t interpret them as options.

```bash
docker rm -f ignition81 2>/dev/null || true
docker volume rm ignition81-data 2>/dev/null || true
docker volume create ignition81-data >/dev/null

docker run -d --name ignition81 \
  -p 8097:8088 \
  -p 8047:8043 \
  -e ACCEPT_IGNITION_EULA=Y \
  -v ignition81-data:/usr/local/bin/ignition/data \
  -v /absolute/path/to/your.gwbk:/restore.gwbk:ro \
  inductiveautomation/ignition:8.1.51 \
  -r /restore.gwbk \
  -- \
  -Dignition.allowunsignedmodules=true
```

Verify:

```bash
curl -I http://localhost:8097/
docker logs --tail 50 ignition81
```

### Docker Compose (recommended)

This folder includes:
- `docker-compose.yml` (normal start)
- `docker-compose.restore.yml` (first-time restore from a `.gwbk`)
- `env.example` (copy to `.env`)

#### 1) Create your local `.env` (not committed)

```bash
cp docker/ignition-gateway/env.example docker/ignition-gateway/.env
```

#### 2) Normal start

```bash
cd docker/ignition-gateway
docker compose up -d
curl -I "http://localhost:${HOST_HTTP_PORT:-8097}/"
```

#### 3) First-time restore from a working gateway (`.gwbk`)

1) Copy your backup into place:

```bash
cp /absolute/path/to/your.gwbk docker/ignition-gateway/restore/restore.gwbk
```

2) Make sure you restore into a **fresh** volume:

```bash
docker compose down -v
```

3) Run the restore compose file:

```bash
cd docker/ignition-gateway
docker compose -f docker-compose.restore.yml up -d
docker logs --tail 80 ignition81
```

### Toggling “dev” vs “non-dev”

This repo’s module dev flow often needs unsigned modules enabled. Prefer doing this as a **runtime JVM arg**:

```bash
-- -Dignition.allowunsignedmodules=true
```

To run in “non-dev”, omit the JVM arg (and rely on signed modules only).

With docker compose, set `IGNITION_ALLOW_UNSIGNED_MODULES=false` in `.env`.


