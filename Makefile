# ──────────────────────────────────────────────────────────────
# Zerobus Ignition - end-to-end from scratch
# ──────────────────────────────────────────────────────────────
#
# Bootstrap (automated steps):
#   make bootstrap-83
#     Step 1  db-create-sp           Create SP, generate OAuth secret, assign to workspace
#     Step 2  db-setup-sql           Create catalog/schema/tables, SP grants
#             db-wheel               Build + upload ot_analytics wheel to UC volume
#             db-deploy              Deploy all DAB resources (app, pipeline, Lakebase, job)
#             db-lakebase-post-deploy  PostgreSQL DDL + grants after DAB creates Lakebase
#     Step 3  build-83               Build Ignition + Zerobus module (.modl)
#     Step 4  up-83                  Start Ignition gateway (opens setup wizard)
#
# Then finish manually:
#   make setup-wizard-83          Step 4b  Complete Ignition setup in browser
#   make configure-83             Step 5   Push SP credentials to gateway
#   make simulate-83              Step 6   Start synthetic data generation
#   make links-83                 Step 7   Print all URLs for easy navigation
#   make db-train-health-model    Step 8   (optional) Run train_health_model job
#
# Full reset (Ignition + Databricks clean, then bootstrap):
#   make db-clean clean-83 bootstrap-83
#   then: make setup-wizard-83 configure-83 simulate-83 links-83
# ──────────────────────────────────────────────────────────────

SHELL := /bin/bash

# Auto-load local overrides when present so `make` picks up
# workspace/profile settings without requiring manual `source .env`.
-include .env

# ── Versions ─────────────────────────────────────────────────
IGNITION_83_TAG       ?= 8.3
IGNITION_83_BUILD_VER ?= 8.3.3
IGNITION_83_MIN_VER   ?= 8.3.0
IGNITION_83_HOME      ?= /usr/local/bin/ignition
# Note: docker/Dockerfile.build-modl now falls back to the SDK patch version
# found in the Ignition image if gateway-api-$(IGNITION_83_BUILD_VER).jar is absent.

IGNITION_81_TAG       ?= 8.1
IGNITION_81_BUILD_VER ?= 8.1.50
IGNITION_81_MIN_VER   ?= 8.1.0
IGNITION_81_HOME      ?= /usr/local/ignition

# ── Ports / Gateway URL ───────────────────────────────────────
PORT_83 ?= 7088
PORT_81 ?= 8097
GATEWAY_URL_83 ?= http://localhost:$(PORT_83)
GATEWAY_URL_81 ?= http://localhost:$(PORT_81)

# ── Zerobus / workspace (set once in .env, used everywhere) ─────
# Source .env before make, or export: DATABRICKS_WAREHOUSE_ID, WORKSPACE_ID, DATABRICKS_REGION
WORKSPACE_ID       ?= 7405609621983921
DATABRICKS_REGION  ?= australiaeast
# ZEROBUS_ENDPOINT: set explicitly or derived from WORKSPACE_ID + DATABRICKS_REGION
ifndef ZEROBUS_ENDPOINT
ZEROBUS_ENDPOINT   = $(WORKSPACE_ID).zerobus.$(DATABRICKS_REGION).azuredatabricks.net
endif
export DATABRICKS_WAREHOUSE_ID WORKSPACE_ID DATABRICKS_REGION ZEROBUS_ENDPOINT

DATABRICKS_CONFIG_PROFILE ?= daveok
# Workspace host from profile (so workspace steps get credentials when DATABRICKS_HOST is unset after db-create-sp)
WS_HOST ?= $(shell awk '/^\[$(DATABRICKS_CONFIG_PROFILE)\]/{found=1} found && /^host/{gsub(/^[^=]+=[ \t]*/,""); print; exit}' ~/.databrickscfg 2>/dev/null)

# ── Databricks / pipeline / app ──────────────────────────────
CATALOG       ?= ot_demo
SCHEMA        ?= ot
DATABRICKS_WAREHOUSE_ID  ?= e4082fdb7ea19a15
# Apply default when DATABRICKS_WAREHOUSE_ID is set but empty (e.g. from .env)
ifeq ($(strip $(DATABRICKS_WAREHOUSE_ID)),)
DATABRICKS_WAREHOUSE_ID  := e4082fdb7ea19a15
endif
PIPELINE_NAME ?= [production] ot-etl
JOB_NAME      ?= [production] ot-train-health-model
APP_NAME      ?= zerobus-ignition-demo
LAKEBASE_INSTANCE_NAME ?= ot-demo-lakebase
LAKEBASE_INSTANCE_CAPACITY ?= CU_1
LAKEBASE_CONNECTOR_ARTIFACT ?= .lakebase-connector.env

# ── Databricks bundle direct engine ───────────────────────────
BUNDLE_ENGINE ?= direct
MIN_DATABRICKS_CLI_MINOR ?= 279

# ── Bundle --var flags (DRY macro used by db-deploy, db-run, etc.) ──
BUNDLE_VARS = \
	--var="catalog=$(CATALOG)" \
	--var="schema=$(SCHEMA)" \
	--var="pipeline_name=$(PIPELINE_NAME)" \
	--var="job_name=$(JOB_NAME)" \
	--var="lakebase_instance_name=$(LAKEBASE_INSTANCE_NAME)" \
	--var="lakebase_instance_capacity=$(LAKEBASE_INSTANCE_CAPACITY)" \
	--var="lakebase_database_name=$(or $(LAKEBASE_DATABASE),databricks_postgres)" \
	--var="connector_role_name=$(or $(CONNECTOR_ROLE_NAME),zerobus_connector)"

# ── Service principal ────────────────────────────────────────
SP_NAME         ?= ignition-zerobus-demo
SP_PROFILE_NAME ?= ot-demo
# Auto-read SP application ID from the SP profile in ~/.databrickscfg.
# Falls back to the hardcoded default if the profile doesn't exist yet.
SP_APPLICATION_ID ?= $(shell awk '/^\[$(SP_PROFILE_NAME)\]/{found=1} found && /^client_id/{gsub(/^[^=]+=[ \t]*/,""); print; exit}' ~/.databrickscfg 2>/dev/null)

# ── Simulator ─────────────────────────────────────────────────
# Volume: events/tick = (sites*units)*23 + sites*16 (BESS+Grid). events/s = events_per_tick * 1000/interval.
# Default (3 sites, 2 units, 1s): ~186 events/tick, ~186 events/s, ~11k/min.
# For data to flow through pipeline/app in ~30-60s, use heavier load e.g.:
#   SIM_SITES=5 SIM_UNITS=4 SIM_INTERVAL=500  -> ~540 events/tick, ~1080 events/s (~65k/min).
SIM_SITES    ?= 3
SIM_UNITS    ?= 2
SIM_INTERVAL ?= 1000
SIM_TICKS    ?= 0
SIM_PROJECT_DIR ?= $(firstword $(wildcard examples/*_fleet))
SIM_ENTRYPOINT ?= $(shell awk -F= 'BEGIN{f=0} /^\[project\.scripts\]/{f=1;next} f && /^[[:space:]]*[A-Za-z0-9_-]+[[:space:]]*=/{gsub(/[[:space:]]/,"",$$1); print $$1; exit}' "$(SIM_PROJECT_DIR)/pyproject.toml" 2>/dev/null)

# ── Azure Container Apps (ACA) ────────────────────────────────
ACR_NAME           ?= daveokacr
ACA_RG             ?= rg-databricks-daveok
ACA_LOCATION       ?= australiaeast
ACA_ENV            ?= ignition-env
ACA_GATEWAY_APP    ?= ignition-zerobus
ACA_SIM_APP        ?= agl-sim
ACA_SIM_IMAGE      ?= $(ACR_NAME).azurecr.io/agl-sim:latest
ACA_GATEWAY_IMAGE  ?= $(ACR_NAME).azurecr.io/ignition-zerobus:8.3.3
ACA_ALLOWED_IP     ?= $(shell curl -sf https://ifconfig.me 2>/dev/null)

# ── Paths ────────────────────────────────────────────────────
COMPOSE_DIR   := docker/ignition-gateway
RELEASES_DIR  := releases
DOCKER_OUT_83 := docker-out/8.3
DOCKER_OUT_81 := docker-out/8.1
SDP_DIR       := pipelines/sdp
WHEEL_FILE    := ot_analytics-0.1.1-py3-none-any.whl

# ──────────────────────────────────────────────────────────────
# Build targets
# ──────────────────────────────────────────────────────────────

.PHONY: build-83
build-83: ## Build the 8.3 .modl (Docker, no local Ignition needed)
	@echo "▸ Building Ignition 8.3 module..."
	DOCKER_BUILDKIT=1 docker build --no-cache \
		-f docker/Dockerfile.build-modl \
		--target out \
		--build-arg IGNITION_TAG=$(IGNITION_83_TAG) \
		--build-arg IGNITION_HOME=$(IGNITION_83_HOME) \
		--build-arg BUILD_FOR_IGNITION_VERSION=$(IGNITION_83_BUILD_VER) \
		--build-arg MIN_IGNITION_VERSION=$(IGNITION_83_MIN_VER) \
		--output type=local,dest=$(DOCKER_OUT_83) .
	@mkdir -p $(RELEASES_DIR)
	cp $(DOCKER_OUT_83)/*.modl $(RELEASES_DIR)/
	@echo "✔ Module(s) copied to $(RELEASES_DIR)/"
	@ls -lh $(RELEASES_DIR)/*.modl

.PHONY: build-81
build-81: ## Build the 8.1 .modl (Docker, no local Ignition needed)
	@echo "▸ Building Ignition 8.1 module..."
	DOCKER_BUILDKIT=1 docker build --no-cache \
		-f docker/Dockerfile.build-modl \
		--target out \
		--build-arg IGNITION_TAG=$(IGNITION_81_TAG) \
		--build-arg IGNITION_HOME=$(IGNITION_81_HOME) \
		--build-arg BUILD_FOR_IGNITION_VERSION=$(IGNITION_81_BUILD_VER) \
		--build-arg MIN_IGNITION_VERSION=$(IGNITION_81_MIN_VER) \
		--output type=local,dest=$(DOCKER_OUT_81) .
	@mkdir -p $(RELEASES_DIR)
	cp $(DOCKER_OUT_81)/*.modl $(RELEASES_DIR)/
	@echo "✔ Module(s) copied to $(RELEASES_DIR)/"
	@ls -lh $(RELEASES_DIR)/*.modl

# ──────────────────────────────────────────────────────────────
# Gateway lifecycle (8.3)
# ──────────────────────────────────────────────────────────────

.PHONY: up-83
up-83: ## Start Ignition 8.3 gateway (fresh volume, module baked in)
	@echo "▸ Resetting volume and starting Ignition 8.3 on port $(PORT_83)..."
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.83.yml down -v 2>/dev/null || true
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.83.yml up -d
	@echo ""
	@echo "✔ Gateway starting on $(GATEWAY_URL_83)"
	@echo "  Complete the setup wizard: make setup-wizard-83"

.PHONY: start-83
start-83: ## Start 8.3 gateway (keep existing volume)
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.83.yml up -d
	@echo "✔ Gateway running on $(GATEWAY_URL_83)"

.PHONY: stop-83
stop-83: ## Stop 8.3 gateway (keep volume)
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.83.yml down

.PHONY: clean-83
clean-83: ## Stop 8.3 gateway and destroy volume
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.83.yml down -v

.PHONY: logs-83
logs-83: ## Tail 8.3 gateway logs
	docker logs --tail 100 -f ignition83_7088

.PHONY: setup-wizard-83
setup-wizard-83: ## Open browser to complete 8.3 setup wizard
	@echo "▸ Opening setup wizard..."
	@echo "  1. Accept EULA"
	@echo "  2. Create admin user (admin / password)"
	@echo "  3. Select Standard Trial"
	@echo "  4. Finish"
	@open "$(GATEWAY_URL_83)" 2>/dev/null || xdg-open "$(GATEWAY_URL_83)" 2>/dev/null || echo "Open $(GATEWAY_URL_83) in your browser"

# ──────────────────────────────────────────────────────────────
# Gateway lifecycle (8.1)
# ──────────────────────────────────────────────────────────────

.PHONY: up-81
up-81: ## Start Ignition 8.1 gateway (fresh volume, module baked in)
	@echo "▸ Resetting volume and starting Ignition 8.1 on port $(PORT_81)..."
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.yml down -v 2>/dev/null || true
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.yml up -d
	@echo ""
	@echo "✔ Gateway starting on $(GATEWAY_URL_81)"

.PHONY: start-81
start-81: ## Start 8.1 gateway (keep existing volume)
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.yml up -d
	@echo "✔ Gateway running on $(GATEWAY_URL_81)"

.PHONY: stop-81
stop-81: ## Stop 8.1 gateway (keep volume)
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.yml down

.PHONY: clean-81
clean-81: ## Stop 8.1 gateway and destroy volume
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.yml down -v

.PHONY: logs-81
logs-81: ## Tail 8.1 gateway logs
	docker logs --tail 100 -f ignition81

# ──────────────────────────────────────────────────────────────
# Restore from .gwbk backup
# ──────────────────────────────────────────────────────────────

.PHONY: restore-83
restore-83: ## Restore 8.3 gateway from restore83/restore.gwbk
	@test -f $(COMPOSE_DIR)/restore83/restore.gwbk || \
		(echo "✘ Place your .gwbk at $(COMPOSE_DIR)/restore83/restore.gwbk first" && exit 1)
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.83.restore.yml down -v 2>/dev/null || true
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.83.restore.yml up -d
	@echo "✔ Restoring 8.3 gateway from backup on $(GATEWAY_URL_83)"

.PHONY: restore-81
restore-81: ## Restore 8.1 gateway from restore/restore.gwbk
	@test -f $(COMPOSE_DIR)/restore/restore.gwbk || \
		(echo "✘ Place your .gwbk at $(COMPOSE_DIR)/restore/restore.gwbk first" && exit 1)
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.restore.yml down -v 2>/dev/null || true
	cd $(COMPOSE_DIR) && docker compose -f docker-compose.restore.yml up -d
	@echo "✔ Restoring 8.1 gateway from backup on $(GATEWAY_URL_81)"

# ──────────────────────────────────────────────────────────────
# Configure Zerobus connection
# ──────────────────────────────────────────────────────────────

.PHONY: configure-83
configure-83: ## Push Databricks/Zerobus config to 8.3 gateway
	@echo "▸ Configuring Zerobus on 8.3 gateway (port $(PORT_83))..."
	@echo "  workspace from profile [$(SP_PROFILE_NAME)]; endpoint=$(ZEROBUS_ENDPOINT); table=$(CATALOG).$(SCHEMA).raw_tags"
	@if [ -z "$(SIM_PROJECT_DIR)" ] || [ -z "$(SIM_ENTRYPOINT)" ]; then \
		echo "✘ Could not locate simulator project/scripts under examples/*_fleet"; \
		exit 1; \
	fi
	cd $(SIM_PROJECT_DIR) && \
		CATALOG=$(CATALOG) SCHEMA=$(SCHEMA) \
		uv run --extra setup $(SIM_ENTRYPOINT) --setup-only \
			--profile $(SP_PROFILE_NAME) \
			--zerobus-endpoint $(ZEROBUS_ENDPOINT) \
			--gateway $(GATEWAY_URL_83)
	@echo "✔ Configuration pushed. Run: make health-83"

.PHONY: configure-81
configure-81: ## Push Databricks/Zerobus config to 8.1 gateway
	@echo "▸ Configuring Zerobus on 8.1 gateway (port $(PORT_81))..."
	@echo "  workspace from profile [$(SP_PROFILE_NAME)]; endpoint=$(ZEROBUS_ENDPOINT); table=$(CATALOG).$(SCHEMA).raw_tags"
	@if [ -z "$(SIM_PROJECT_DIR)" ] || [ -z "$(SIM_ENTRYPOINT)" ]; then \
		echo "✘ Could not locate simulator project/scripts under examples/*_fleet"; \
		exit 1; \
	fi
	cd $(SIM_PROJECT_DIR) && \
		CATALOG=$(CATALOG) SCHEMA=$(SCHEMA) \
		uv run --extra setup $(SIM_ENTRYPOINT) --setup-only \
			--profile $(SP_PROFILE_NAME) \
			--zerobus-endpoint $(ZEROBUS_ENDPOINT) \
			--gateway $(GATEWAY_URL_81)
	@echo "✔ Configuration pushed. Run: make health-81"

.PHONY: configure-postgres-83
configure-postgres-83: ## Enable PostgreSQL sink on 8.3 gateway (requires LAKEBASE_* env vars)
	@if [ -z "$(LAKEBASE_HOST)" ] || [ -z "$(LAKEBASE_USER)" ] || [ -z "$(LAKEBASE_PASSWORD)" ]; then \
		echo "✘ Missing Lakebase env vars. Set LAKEBASE_HOST, LAKEBASE_USER, LAKEBASE_PASSWORD in .env"; \
		exit 1; \
	fi
	@echo "▸ Enabling PostgreSQL sink on 8.3 gateway (merging with existing config)..."
	@python3 -c " \
import json, urllib.request; \
current = json.loads(urllib.request.urlopen('$(GATEWAY_URL_83)/system/zerobus/config').read()); \
current.update({ \
    'sinkMode': 'lakebase', \
    'enableZerobusSink': False, \
    'enablePostgresSink': True, \
    'postgresHost': '$(LAKEBASE_HOST)', \
    'postgresPort': $(or $(LAKEBASE_PORT),5432), \
    'postgresDatabase': '$(or $(LAKEBASE_DATABASE),databricks_postgres)', \
    'postgresUser': '$(LAKEBASE_USER)', \
    'postgresPassword': '$(LAKEBASE_PASSWORD)', \
    'postgresTable': '$(or $(LAKEBASE_TABLE),raw_tags)' \
}); \
req = urllib.request.Request('$(GATEWAY_URL_83)/system/zerobus/config', \
    data=json.dumps(current).encode(), headers={'Content-Type': 'application/json'}); \
resp = json.loads(urllib.request.urlopen(req).read()); \
print('✔ PostgreSQL sink enabled' if resp.get('success') else '✘ ' + resp.get('message', 'Unknown error')) \
"

.PHONY: configure-postgres-81
configure-postgres-81: ## Enable PostgreSQL sink on 8.1 gateway (requires LAKEBASE_* env vars)
	@if [ -z "$(LAKEBASE_HOST)" ] || [ -z "$(LAKEBASE_USER)" ] || [ -z "$(LAKEBASE_PASSWORD)" ]; then \
		echo "✘ Missing Lakebase env vars. Set LAKEBASE_HOST, LAKEBASE_USER, LAKEBASE_PASSWORD in .env"; \
		exit 1; \
	fi
	@echo "▸ Enabling PostgreSQL sink on 8.1 gateway (merging with existing config)..."
	@python3 -c " \
import json, urllib.request; \
current = json.loads(urllib.request.urlopen('$(GATEWAY_URL_81)/system/zerobus/config').read()); \
current.update({ \
    'sinkMode': 'lakebase', \
    'enableZerobusSink': False, \
    'enablePostgresSink': True, \
    'postgresHost': '$(LAKEBASE_HOST)', \
    'postgresPort': $(or $(LAKEBASE_PORT),5432), \
    'postgresDatabase': '$(or $(LAKEBASE_DATABASE),databricks_postgres)', \
    'postgresUser': '$(LAKEBASE_USER)', \
    'postgresPassword': '$(LAKEBASE_PASSWORD)', \
    'postgresTable': '$(or $(LAKEBASE_TABLE),raw_tags)' \
}); \
req = urllib.request.Request('$(GATEWAY_URL_81)/system/zerobus/config', \
    data=json.dumps(current).encode(), headers={'Content-Type': 'application/json'}); \
resp = json.loads(urllib.request.urlopen(req).read()); \
print('✔ PostgreSQL sink enabled' if resp.get('success') else '✘ ' + resp.get('message', 'Unknown error')) \
"

.PHONY: configure-zerobus-83
configure-zerobus-83: configure-83 ## Force Zerobus-only mode on 8.3 gateway
	@echo "▸ Forcing Zerobus-only sink mode on 8.3 gateway..."
	@python3 -c " \
import json, urllib.request; \
current = json.loads(urllib.request.urlopen('$(GATEWAY_URL_83)/system/zerobus/config').read()); \
current.update({ \
    'sinkMode': 'zerobus', \
    'enableZerobusSink': True, \
    'enablePostgresSink': False \
}); \
req = urllib.request.Request('$(GATEWAY_URL_83)/system/zerobus/config', \
    data=json.dumps(current).encode(), headers={'Content-Type': 'application/json'}); \
resp = json.loads(urllib.request.urlopen(req).read()); \
print('✔ Zerobus-only mode enabled' if resp.get('success') else '✘ ' + resp.get('message', 'Unknown error')) \
"

.PHONY: configure-lakebase-83
configure-lakebase-83: configure-83 configure-postgres-83 ## Force Lakebase-only mode on 8.3 gateway
	@echo "✔ Lakebase-only mode configured on 8.3 gateway"

.PHONY: configure-lakebase-83-direct
configure-lakebase-83-direct: configure-83 db-lakebase-provision-direct ## Provision Lakebase + configure 8.3 gateway in Lakebase mode
	@echo "▸ Applying direct-provisioned Lakebase connector credentials to 8.3 gateway..."
	@if [ ! -f "$(LAKEBASE_CONNECTOR_ARTIFACT)" ]; then \
		echo "✘ Connector artifact not found: $(LAKEBASE_CONNECTOR_ARTIFACT)"; \
		echo "  Run: make db-lakebase-provision-direct"; \
		exit 1; \
	fi
	@set -a && source "$(LAKEBASE_CONNECTOR_ARTIFACT)" && set +a && \
		$(MAKE) configure-postgres-83 \
			LAKEBASE_HOST="$$LAKEBASE_HOST" \
			LAKEBASE_PORT="$$LAKEBASE_PORT" \
			LAKEBASE_DATABASE="$$LAKEBASE_DATABASE" \
			LAKEBASE_USER="$$LAKEBASE_USER" \
			LAKEBASE_PASSWORD="$$LAKEBASE_PASSWORD" \
			LAKEBASE_TABLE="$$LAKEBASE_TABLE"

.PHONY: configure-zerobus-81
configure-zerobus-81: configure-81 ## Force Zerobus-only mode on 8.1 gateway
	@echo "▸ Forcing Zerobus-only sink mode on 8.1 gateway..."
	@python3 -c " \
import json, urllib.request; \
current = json.loads(urllib.request.urlopen('$(GATEWAY_URL_81)/system/zerobus/config').read()); \
current.update({ \
    'sinkMode': 'zerobus', \
    'enableZerobusSink': True, \
    'enablePostgresSink': False \
}); \
req = urllib.request.Request('$(GATEWAY_URL_81)/system/zerobus/config', \
    data=json.dumps(current).encode(), headers={'Content-Type': 'application/json'}); \
resp = json.loads(urllib.request.urlopen(req).read()); \
print('✔ Zerobus-only mode enabled' if resp.get('success') else '✘ ' + resp.get('message', 'Unknown error')) \
"

.PHONY: configure-lakebase-81
configure-lakebase-81: configure-81 configure-postgres-81 ## Force Lakebase-only mode on 8.1 gateway
	@echo "✔ Lakebase-only mode configured on 8.1 gateway"

.PHONY: configure-lakebase-81-direct
configure-lakebase-81-direct: configure-81 db-lakebase-provision-direct ## Provision Lakebase + configure 8.1 gateway in Lakebase mode
	@echo "▸ Applying direct-provisioned Lakebase connector credentials to 8.1 gateway..."
	@if [ ! -f "$(LAKEBASE_CONNECTOR_ARTIFACT)" ]; then \
		echo "✘ Connector artifact not found: $(LAKEBASE_CONNECTOR_ARTIFACT)"; \
		echo "  Run: make db-lakebase-provision-direct"; \
		exit 1; \
	fi
	@set -a && source "$(LAKEBASE_CONNECTOR_ARTIFACT)" && set +a && \
		$(MAKE) configure-postgres-81 \
			LAKEBASE_HOST="$$LAKEBASE_HOST" \
			LAKEBASE_PORT="$$LAKEBASE_PORT" \
			LAKEBASE_DATABASE="$$LAKEBASE_DATABASE" \
			LAKEBASE_USER="$$LAKEBASE_USER" \
			LAKEBASE_PASSWORD="$$LAKEBASE_PASSWORD" \
			LAKEBASE_TABLE="$$LAKEBASE_TABLE"

# ──────────────────────────────────────────────────────────────
# Health & diagnostics
# ──────────────────────────────────────────────────────────────

.PHONY: health-83
health-83: ## Health check on 8.3 gateway
	@curl -sf $(GATEWAY_URL_83)/system/zerobus/health && echo "" || \
		echo "✘ Gateway not responding on port $(PORT_83)"

.PHONY: health-81
health-81: ## Health check on 8.1 gateway
	@curl -sf $(GATEWAY_URL_81)/system/zerobus/health && echo "" || \
		echo "✘ Gateway not responding on port $(PORT_81)"

.PHONY: diag-83
diag-83: ## Full diagnostics on 8.3 gateway (plain text)
	@code=$$(curl -s -o /tmp/diag_83_resp -w "%{http_code}" $(GATEWAY_URL_83)/system/zerobus/diagnostics 2>/dev/null); \
	if [ -z "$$code" ] || [ "$$code" = "000" ]; then echo "✘ Gateway not responding on port $(PORT_83) (connection refused or unreachable)"; exit 1; fi; \
	if [ "$$code" != "200" ]; then echo "✘ Gateway returned HTTP $$code:"; cat /tmp/diag_83_resp 2>/dev/null; exit 1; fi; \
	cat /tmp/diag_83_resp

.PHONY: diag-81
diag-81: ## Full diagnostics on 8.1 gateway (plain text)
	@code=$$(curl -s -o /tmp/diag_81_resp -w "%{http_code}" $(GATEWAY_URL_81)/system/zerobus/diagnostics 2>/dev/null); \
	if [ -z "$$code" ] || [ "$$code" = "000" ]; then echo "✘ Gateway not responding on port $(PORT_81) (connection refused or unreachable)"; exit 1; fi; \
	if [ "$$code" != "200" ]; then echo "✘ Gateway returned HTTP $$code:"; cat /tmp/diag_81_resp 2>/dev/null; exit 1; fi; \
	cat /tmp/diag_81_resp

# ──────────────────────────────────────────────────────────────
# Zerobus SDK connectivity test (create table then run SDK)
# ──────────────────────────────────────────────────────────────

.PHONY: zerobus-test-table
zerobus-test-table: ## Create ot_demo.ot.zerobus_test and grant SP UC write (run db-setup-sql first)
	@echo "▸ Creating $(CATALOG).$(SCHEMA).zerobus_test and granting SP $(SP_APPLICATION_ID) MODIFY, SELECT..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	CATALOG=$(CATALOG) SCHEMA=$(SCHEMA) DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
	SP_APPLICATION_ID="$(SP_APPLICATION_ID)" \
		uv run --with databricks-sdk python onboarding/databricks/create_zerobus_test_table.py
	@echo "✔ Table and UC grants ready"

.PHONY: zerobus-test
zerobus-test: zerobus-test-table ## Create zerobus_test table then run Zerobus SDK test (load .env for credentials)
	@echo "▸ Running Zerobus SDK test (table=$(CATALOG).$(SCHEMA).zerobus_test)..."
	@if [ ! -f .env ]; then echo "✘ .env not found. Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in .env"; exit 1; fi; \
	export $$(grep -v '^#' .env | xargs) 2>/dev/null; \
	export ZEROBUS_TARGET_TABLE="$(CATALOG).$(SCHEMA).zerobus_test"; \
	cd zerobus-test && uv run python test_zerobus.py

.PHONY: test-connection-83
test-connection-83: ## Validate Zerobus auth from inside Ignition (POST test-connection)
	@echo "▸ Testing Zerobus connection on 8.3 gateway..."
	@resp=$$(curl -s -X POST -H "Content-Type: application/json" $(GATEWAY_URL_83)/system/zerobus/test-connection 2>/dev/null); \
	if [ -z "$$resp" ]; then echo "✘ Gateway not responding on port $(PORT_83)"; exit 1; fi; \
	success=$$(echo "$$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success', False))" 2>/dev/null); \
	msg=$$(echo "$$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',''))" 2>/dev/null); \
	if [ "$$success" = "True" ]; then echo "✔ $$msg"; exit 0; else echo "✘ $$msg"; echo "  Run make diag-83 for full diagnostics."; exit 1; fi

.PHONY: test-connection-81
test-connection-81: ## Validate Zerobus auth from inside Ignition (POST test-connection)
	@echo "▸ Testing Zerobus connection on 8.1 gateway..."
	@resp=$$(curl -s -X POST -H "Content-Type: application/json" $(GATEWAY_URL_81)/system/zerobus/test-connection 2>/dev/null); \
	if [ -z "$$resp" ]; then echo "✘ Gateway not responding on port $(PORT_81)"; exit 1; fi; \
	success=$$(echo "$$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success', False))" 2>/dev/null); \
	msg=$$(echo "$$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',''))" 2>/dev/null); \
	if [ "$$success" = "True" ]; then echo "✔ $$msg"; exit 0; else echo "✘ $$msg"; echo "  Run make diag-81 for full diagnostics."; exit 1; fi

# ══════════════════════════════════════════════════════════════
# DATABRICKS - SP, catalog setup, wheel, bundle deploy
# ══════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────
# Service principal (account-level create + workspace assign)
# ──────────────────────────────────────────────────────────────

# Clears the Databricks CLI token cache so the next account-level call re-authenticates.
# Use when you see "Endpoint not found" for account SCIM after re-running databricks auth login.
.PHONY: db-clear-account-cache
db-clear-account-cache: ## Clear CLI token cache so account auth is re-prompted
	@rm -f ~/.databricks/token-cache.json && \
	echo "✔ Cleared ~/.databricks/token-cache.json" && \
	echo "" && \
	echo "Re-authenticate at the account level, then run db-create-sp:" && \
	echo "  databricks auth login --host https://accounts.azuredatabricks.net --account-id ccb842e7-2376-4152-b0b0-29fa952379b8" && \
	echo "  make db-create-sp"

.PHONY: db-create-sp
db-create-sp: ## Create SP, generate OAuth secret, write ~/.databrickscfg profile
	@echo "▸ Creating service principal '$(SP_NAME)'..."
	@# Unset DATABRICKS_HOST so AccountClient uses the account profile host (accounts.azuredatabricks.net), not workspace URL
	CATALOG=$(CATALOG) \
	SCHEMA=$(SCHEMA) \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
	DATABRICKS_HOST= \
		uv run --with databricks-sdk python onboarding/databricks/create_service_principal.py \
			--sp-name "$(SP_NAME)" \
			--profile-name "$(SP_PROFILE_NAME)" \
			--workspace-profile "$(DATABRICKS_CONFIG_PROFILE)"

.PHONY: db-create-sp-no-grants
db-create-sp-no-grants: ## Create SP without running UC grants
	@echo "▸ Creating service principal '$(SP_NAME)' (skip grants)..."
	uv run --with databricks-sdk python onboarding/databricks/create_service_principal.py \
		--sp-name "$(SP_NAME)" \
		--profile-name "$(SP_PROFILE_NAME)" \
		--workspace-profile "$(DATABRICKS_CONFIG_PROFILE)" \
		--skip-grants

.PHONY: db-check-sp
db-check-sp: ## Check [ot-demo] profile and verify SP OAuth secret works
	@echo "▸ Checking SP profile [$(SP_PROFILE_NAME)] and secret..."
	SP_PROFILE_NAME="$(SP_PROFILE_NAME)" uv run --with databricks-sdk python onboarding/databricks/check_sp_and_secret.py
	@echo "✔ SP and secret OK. Use this profile for: make configure-83"

# Print the command to log in to the workspace (profile [daveok]). Use when db-setup-sql fails with "cannot configure default credentials".
.PHONY: db-login-workspace
db-login-workspace: ## Print command to log in to workspace (run it, then retry db-setup-sql)
	@WS_HOST="$(WS_HOST)"; \
	if [ -z "$$WS_HOST" ]; then \
		echo "✘ Could not read host from profile [$(DATABRICKS_CONFIG_PROFILE)] in ~/.databrickscfg"; \
		echo "  Ensure [$(DATABRICKS_CONFIG_PROFILE)] has a 'host' line (workspace URL)."; \
		exit 1; \
	fi; \
	echo "▸ Log in to the workspace so db-setup-sql can use profile [$(DATABRICKS_CONFIG_PROFILE)]:"; \
	echo ""; \
	echo "  databricks auth login --host $$WS_HOST"; \
	echo ""; \
	echo "Then run: make db-setup-sql"

# ──────────────────────────────────────────────────────────────
# Catalog / schema / tables / grants
# ──────────────────────────────────────────────────────────────

.PHONY: db-setup-sql
db-setup-sql: ## Run setup SQL (catalog, schema, tables, SP grants)
	@echo "▸ Running setup SQL (catalog=$(CATALOG), schema=$(SCHEMA), SP=$(SP_APPLICATION_ID))..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	CATALOG=$(CATALOG) \
	SCHEMA=$(SCHEMA) \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
	SP_APPLICATION_ID=$(SP_APPLICATION_ID) \
	SKIP_CATALOG_CREATE=$(SKIP_CATALOG_CREATE) \
		uv run --with databricks-sdk python onboarding/databricks/run_setup_sql.py
	@echo "✔ Setup SQL complete"

.PHONY: db-grant-app-sp
db-grant-app-sp: ## Grant UC privileges to Databricks App SP (run after db-deploy)
	@echo "▸ Granting UC privileges to app SP (app=$(APP_NAME), catalog=$(CATALOG).$(SCHEMA))..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	APP_NAME=$(APP_NAME) \
	CATALOG=$(CATALOG) \
	SCHEMA=$(SCHEMA) \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
		uv run --with databricks-sdk python onboarding/databricks/uc_grants.py
	@echo "✔ App SP grants complete"

# ──────────────────────────────────────────────────────────────
# Lakebase (PostgreSQL) setup
# ──────────────────────────────────────────────────────────────

# Lakebase env vars: LAKEBASE_HOST, LAKEBASE_PORT, LAKEBASE_DATABASE, LAKEBASE_USER, LAKEBASE_PASSWORD
# Set in .env and source before running Lakebase targets.

.PHONY: db-lakebase-setup
db-lakebase-setup: ## Create raw_tags table in Lakebase (requires LAKEBASE_* env vars)
	@if [ -z "$(LAKEBASE_HOST)" ] || [ -z "$(LAKEBASE_DATABASE)" ] || [ -z "$(LAKEBASE_USER)" ] || [ -z "$(LAKEBASE_PASSWORD)" ]; then \
		echo "✘ Missing Lakebase env vars. Set LAKEBASE_HOST, LAKEBASE_DATABASE, LAKEBASE_USER, LAKEBASE_PASSWORD in .env"; \
		exit 1; \
	fi
	@echo "▸ Creating raw_tags table in Lakebase ($(LAKEBASE_HOST)/$(LAKEBASE_DATABASE))..."
	PGPASSWORD="$(LAKEBASE_PASSWORD)" PGSSLMODE=require psql \
		-h "$(LAKEBASE_HOST)" \
		-p "$(or $(LAKEBASE_PORT),5432)" \
		-U "$(LAKEBASE_USER)" \
		-d "$(LAKEBASE_DATABASE)" \
		-f onboarding/lakebase/create_raw_tags.sql
	@echo "✔ Lakebase table created"

.PHONY: db-lakebase-test
db-lakebase-test: ## Test Lakebase connection (SELECT 1)
	@if [ -z "$(LAKEBASE_HOST)" ] || [ -z "$(LAKEBASE_USER)" ] || [ -z "$(LAKEBASE_PASSWORD)" ]; then \
		echo "✘ Missing Lakebase env vars"; exit 1; \
	fi
	@echo "▸ Testing Lakebase connection..."
	@PGPASSWORD="$(LAKEBASE_PASSWORD)" PGSSLMODE=require psql \
		-h "$(LAKEBASE_HOST)" \
		-p "$(or $(LAKEBASE_PORT),5432)" \
		-U "$(LAKEBASE_USER)" \
		-d "$(or $(LAKEBASE_DATABASE),databricks_postgres)" \
		-c "SELECT 1 AS connected" && echo "✔ Lakebase connection OK" || echo "✘ Connection failed"

.PHONY: db-lakebase-provision-direct
db-lakebase-provision-direct: ## Provision Lakebase via SDK/CLI + create connector role + grants + connector artifact
	@if [ -z "$(LAKEBASE_USER)" ] || [ -z "$(LAKEBASE_PASSWORD)" ]; then \
		echo "▸ LAKEBASE_USER/LAKEBASE_PASSWORD not set; provisioning script will auto-generate a short-lived admin credential from profile [$(DATABRICKS_CONFIG_PROFILE)]."; \
	fi
	@echo "▸ Provisioning Lakebase direct deployment artifacts..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	CATALOG=$(CATALOG) \
	SCHEMA=$(SCHEMA) \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
	SP_PROFILE_NAME=$(SP_PROFILE_NAME) \
	SP_APPLICATION_ID=$(SP_APPLICATION_ID) \
	LAKEBASE_INSTANCE_NAME=$(LAKEBASE_INSTANCE_NAME) \
	LAKEBASE_INSTANCE_CAPACITY=$(LAKEBASE_INSTANCE_CAPACITY) \
	LAKEBASE_DATABASE=$(or $(LAKEBASE_DATABASE),databricks_postgres) \
	LAKEBASE_PORT=$(or $(LAKEBASE_PORT),5432) \
	LAKEBASE_USER=$(LAKEBASE_USER) \
	LAKEBASE_PASSWORD=$(LAKEBASE_PASSWORD) \
	LAKEBASE_TABLE=$(or $(LAKEBASE_TABLE),raw_tags) \
	CONNECTOR_ROLE_NAME=$(or $(CONNECTOR_ROLE_NAME),zerobus_connector) \
	LAKEBASE_CONNECTOR_ARTIFACT=$(LAKEBASE_CONNECTOR_ARTIFACT) \
		uv run --with databricks-sdk --with psycopg[binary] python onboarding/databricks/provision_lakebase_direct.py
	@echo "✔ Direct Lakebase provisioning complete"

# ──────────────────────────────────────────────────────────────
# DAB bundle deploy / run / destroy
# ──────────────────────────────────────────────────────────────

.PHONY: db-deploy
db-deploy: db-bundle-preflight-direct ## Deploy all DAB resources (app, pipeline, Lakebase, job)
	@echo "▸ Deploying all resources via DAB (direct engine)..."
	@set -e; \
	if ! DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
		DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
		DATABRICKS_BUNDLE_ENGINE=$(BUNDLE_ENGINE) \
			databricks bundle deploy -t production $(BUNDLE_VARS) --auto-approve; then \
		echo "  ↻ Deploy failed; resetting bundle state and retrying once..."; \
		DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
		DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
		DATABRICKS_BUNDLE_ENGINE=$(BUNDLE_ENGINE) \
			databricks bundle destroy -t production $(BUNDLE_VARS) --auto-approve || true; \
		DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
		DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
		DATABRICKS_BUNDLE_ENGINE=$(BUNDLE_ENGINE) \
			databricks bundle deploy -t production $(BUNDLE_VARS) --auto-approve; \
	fi
	@echo "✔ Bundle deploy complete"

.PHONY: db-run
db-run: ## Start app + pipeline via DAB bundle run
	@echo "▸ Starting app via bundle run..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	DATABRICKS_BUNDLE_ENGINE=$(BUNDLE_ENGINE) \
		databricks bundle run zerobus_ignition_demo -t production $(BUNDLE_VARS)
	@echo "✔ App started"

.PHONY: db-clean
db-clean: ## Destroy DAB resources + drop catalog CASCADE (clean Databricks for full reset)
	@echo "▸ Destroying DAB bundle resources..."
	-DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	DATABRICKS_BUNDLE_ENGINE=$(BUNDLE_ENGINE) \
		databricks bundle destroy -t production $(BUNDLE_VARS) --auto-approve
	@echo "▸ Cleaning remaining Databricks resources (catalog=$(CATALOG))..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	CATALOG=$(CATALOG) \
	PIPELINE_NAME="$(PIPELINE_NAME)" \
	JOB_NAME="$(JOB_NAME)" \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
		uv run --with databricks-sdk python onboarding/databricks/clean_databricks.py \
			--skip-pipeline --skip-app --skip-job
	@echo "✔ Databricks clean complete"

.PHONY: db-nuke
db-nuke: ## Hard reset Databricks (force delete app/pipeline/job + drop catalog)
	@echo "▸ Hard reset: destroy DAB state (best-effort)..."
	-DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	DATABRICKS_BUNDLE_ENGINE=$(BUNDLE_ENGINE) \
		databricks bundle destroy -t production $(BUNDLE_VARS) --auto-approve
	@echo "▸ Hard reset: force delete resources and catalog..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	CATALOG=$(CATALOG) \
	PIPELINE_NAME="$(PIPELINE_NAME)" \
	JOB_NAME="$(JOB_NAME)" \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
		uv run --with databricks-sdk python onboarding/databricks/clean_databricks.py
	@echo "✔ Databricks hard reset complete"

.PHONY: db-lakebase-post-deploy
db-lakebase-post-deploy: ## Run PostgreSQL DDL + grants after DAB creates Lakebase instance
	@echo "▸ Running post-deploy Lakebase provisioning (DDL + grants)..."
	$(MAKE) db-lakebase-provision-direct
	@echo "✔ Lakebase post-deploy complete"

# ──────────────────────────────────────────────────────────────
# Wheel build + upload to UC volume
# ──────────────────────────────────────────────────────────────

.PHONY: db-wheel-build
db-wheel-build: ## Build ot_analytics wheel
	@echo "▸ Building wheel..."
	uv build $(SDP_DIR)
	@echo "✔ Wheel built: $(SDP_DIR)/dist/$(WHEEL_FILE)"

.PHONY: db-wheel-upload
db-wheel-upload: ## Upload ot_analytics wheel to UC volume
	@test -f $(SDP_DIR)/dist/$(WHEEL_FILE) || \
		(echo "✘ Wheel not found. Run: make db-wheel-build" && exit 1)
	@echo "▸ Uploading wheel to /Volumes/$(CATALOG)/$(SCHEMA)/wheels/$(WHEEL_FILE)..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
		databricks fs cp $(SDP_DIR)/dist/$(WHEEL_FILE) \
			"dbfs:/Volumes/$(CATALOG)/$(SCHEMA)/wheels/$(WHEEL_FILE)" --overwrite
	@echo "✔ Wheel uploaded"

.PHONY: db-wheel
db-wheel: db-wheel-build db-wheel-upload ## Build + upload wheel to UC volume

# ──────────────────────────────────────────────────────────────
# BOM Weather Demo (Databricks 101 bolt-on)
# ──────────────────────────────────────────────────────────────

.PHONY: db-demo-101-deploy
db-demo-101-deploy: ## Deploy pipeline with BOM weather + NEMWEB market tables (all live-fetched)
	@echo "▸ Deploying pipeline with Databricks 101 demo tables..."
	$(MAKE) db-deploy
	@echo "✔ Databricks 101 demo ready — all data fetched live on each pipeline refresh"
	@echo ""
	@echo "  BOM Weather (bom.gov.au):"
	@echo "    bom_raw_observations (Bronze)  bom_validated_observations (Silver)"
	@echo "    bom_station_daily_summary (Gold)  bom_current_conditions (Gold)"
	@echo ""
	@echo "  NEM Market (nemweb.com.au):"
	@echo "    nem_dispatch_prices (Silver)  nem_dispatch_demand (Silver)"
	@echo "    nem_market_snapshot (Gold)"

# ──────────────────────────────────────────────────────────────
# Training job
# ──────────────────────────────────────────────────────────────

.PHONY: db-train-health-model
db-train-health-model: ## Run train_health_model job via DAB bundle run
	@echo "▸ Running train_health_model job..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	DATABRICKS_BUNDLE_ENGINE=$(BUNDLE_ENGINE) \
		databricks bundle run train_health_model -t production $(BUNDLE_VARS)
	@echo "✔ Training job complete"

.PHONY: db-verify-ml
db-verify-ml: ## Run health_scores verification query; exit 0 if ML path active (ml_health non-null)
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	CATALOG=$(CATALOG) \
	SCHEMA=$(SCHEMA) \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
		uv run --with databricks-sdk python onboarding/databricks/verify_ml_health.py

# ──────────────────────────────────────────────────────────────
# Bundle preflight + migration
# ──────────────────────────────────────────────────────────────

.PHONY: db-bundle-preflight-direct
db-bundle-preflight-direct: ## Validate Databricks CLI supports DAB direct engine (>= 0.279.0)
	@if ! command -v databricks >/dev/null 2>&1; then \
		echo "✘ Databricks CLI not found in PATH"; \
		exit 1; \
	fi
	@ver="$$(databricks version 2>/dev/null | sed -E 's/.*([0-9]+\.[0-9]+\.[0-9]+).*/\1/' | awk 'NR==1{print $$1}')"; \
	if [ -z "$$ver" ]; then \
		echo "✘ Could not parse Databricks CLI version"; \
		echo "  Install/upgrade CLI to >= 0.$(MIN_DATABRICKS_CLI_MINOR).0"; \
		exit 1; \
	fi; \
	major="$$(echo $$ver | cut -d. -f1)"; \
	minor="$$(echo $$ver | cut -d. -f2)"; \
	if [ "$$major" -eq 0 ] && [ "$$minor" -lt "$(MIN_DATABRICKS_CLI_MINOR)" ]; then \
		echo "✘ Databricks CLI $$ver is too old for direct deployment engine"; \
		echo "  Upgrade to >= 0.$(MIN_DATABRICKS_CLI_MINOR).0"; \
		exit 1; \
	fi; \
	echo "✔ Databricks CLI $$ver supports direct deployment engine"

.PHONY: db-migrate-to-dab
db-migrate-to-dab: ## One-time: delete SDK-managed pipeline + job before first DAB deploy
	@echo "▸ Deleting SDK-managed resources so DAB can recreate them..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	CATALOG=$(CATALOG) \
	PIPELINE_NAME="$(PIPELINE_NAME)" \
	JOB_NAME="$(JOB_NAME)" \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
		uv run --with databricks-sdk python onboarding/databricks/clean_databricks.py \
			--skip-catalog --skip-app
	@echo "✔ SDK-managed pipeline and job deleted. Run: make db-deploy"

.PHONY: db-recreate-pipeline
db-recreate-pipeline: ## Delete existing Lakeflow pipeline (if present) so deploy recreates it
	@echo "▸ Deleting existing Lakeflow pipeline (if present)..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_HOST=$(or $(DATABRICKS_HOST),$(WS_HOST)) \
	CATALOG=$(CATALOG) \
	PIPELINE_NAME="$(PIPELINE_NAME)" \
	JOB_NAME="$(JOB_NAME)" \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
		uv run --with databricks-sdk python onboarding/databricks/clean_databricks.py \
			--skip-catalog --skip-app --skip-job
	@echo "✔ Pipeline delete check complete"

# ──────────────────────────────────────────────────────────────
# Historical data backfill (synthetic data for time-travel demo)
# ──────────────────────────────────────────────────────────────

BACKFILL_DAYS    ?= 7
BACKFILL_INTERVAL_SEC ?= 300

.PHONY: db-backfill
db-backfill: ## Backfill N days of synthetic data via Spark Connect (BACKFILL_DAYS=7)
	@echo "▸ Backfilling $(BACKFILL_DAYS) days via Serverless Spark Connect..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	CATALOG=$(CATALOG) SCHEMA=$(SCHEMA) BACKFILL_MODE=spark \
	BACKFILL_DAYS=$(BACKFILL_DAYS) BACKFILL_INTERVAL_SEC=$(BACKFILL_INTERVAL_SEC) \
	uv run --with 'databricks-connect' python onboarding/databricks/backfill_historical_data.py

.PHONY: db-backfill-sql
db-backfill-sql: ## Backfill N days via SQL warehouse (slower, no Spark dep)
	@echo "▸ Backfilling $(BACKFILL_DAYS) days via SQL warehouse..."
	DATABRICKS_CONFIG_PROFILE=$(DATABRICKS_CONFIG_PROFILE) \
	DATABRICKS_WAREHOUSE_ID=$(DATABRICKS_WAREHOUSE_ID) \
	CATALOG=$(CATALOG) SCHEMA=$(SCHEMA) BACKFILL_MODE=sql \
	BACKFILL_DAYS=$(BACKFILL_DAYS) BACKFILL_INTERVAL_SEC=$(BACKFILL_INTERVAL_SEC) \
	uv run --with databricks-sdk python onboarding/databricks/backfill_historical_data.py

.PHONY: db-backfill-dry-run
db-backfill-dry-run: ## Preview backfill row count without inserting
	@DRY_RUN=1 BACKFILL_DAYS=$(BACKFILL_DAYS) BACKFILL_INTERVAL_SEC=$(BACKFILL_INTERVAL_SEC) \
	CATALOG=$(CATALOG) SCHEMA=$(SCHEMA) \
	uv run --with databricks-sdk python onboarding/databricks/backfill_historical_data.py

# ──────────────────────────────────────────────────────────────
# Simulator (synthetic OT data generation)
# ──────────────────────────────────────────────────────────────

.PHONY: simulate-83
simulate-83: ## [Step 6] Start synthetic data generation against 8.3 gateway
	@echo "▸ Starting Fleet Simulator ($(SIM_SITES) sites, $(SIM_UNITS) units/site)..."
	@if [ -z "$(SIM_PROJECT_DIR)" ] || [ -z "$(SIM_ENTRYPOINT)" ]; then \
		echo "✘ Could not locate simulator project/scripts under examples/*_fleet"; \
		exit 1; \
	fi
	cd $(SIM_PROJECT_DIR) && \
		uv run $(SIM_ENTRYPOINT) \
			--gateway $(GATEWAY_URL_83) \
			--sites $(SIM_SITES) \
			--units $(SIM_UNITS) \
			--interval $(SIM_INTERVAL) \
			--ticks $(SIM_TICKS)

.PHONY: simulate-81
simulate-81: ## Start synthetic data generation against 8.1 gateway
	@if [ -z "$(SIM_PROJECT_DIR)" ] || [ -z "$(SIM_ENTRYPOINT)" ]; then \
		echo "✘ Could not locate simulator project/scripts under examples/*_fleet"; \
		exit 1; \
	fi
	cd $(SIM_PROJECT_DIR) && \
		uv run $(SIM_ENTRYPOINT) \
			--gateway $(GATEWAY_URL_81) \
			--sites $(SIM_SITES) \
			--units $(SIM_UNITS) \
			--interval $(SIM_INTERVAL) \
			--ticks $(SIM_TICKS)

.PHONY: simulate-heavy-83
simulate-heavy-83: ## [Step 6] Heavy simulation (5 sites, 4 units, 500ms) against 8.3 gateway
	@echo "▸ Starting Fleet Simulator HEAVY (5 sites, 4 units, 500ms)..."
	@if [ -z "$(SIM_PROJECT_DIR)" ] || [ -z "$(SIM_ENTRYPOINT)" ]; then \
		echo "✘ Could not locate simulator project/scripts under examples/*_fleet"; \
		exit 1; \
	fi
	cd $(SIM_PROJECT_DIR) && \
		uv run $(SIM_ENTRYPOINT) \
			--gateway $(GATEWAY_URL_83) \
			--sites 5 \
			--units 4 \
			--interval 500 \
			--ticks $(SIM_TICKS)

.PHONY: simulate-dry-run
simulate-dry-run: ## Dry-run simulator (generate events, don't send)
	@if [ -z "$(SIM_PROJECT_DIR)" ] || [ -z "$(SIM_ENTRYPOINT)" ]; then \
		echo "✘ Could not locate simulator project/scripts under examples/*_fleet"; \
		exit 1; \
	fi
	cd $(SIM_PROJECT_DIR) && \
		uv run $(SIM_ENTRYPOINT) --dry-run \
			--sites $(SIM_SITES) \
			--units $(SIM_UNITS) \
			--ticks 10

# ──────────────────────────────────────────────────────────────
# Links / status (all URLs for easy navigation)
# ──────────────────────────────────────────────────────────────

.PHONY: links-83
links-83: ## [Step 7] Print all URLs for workspace, Zerobus, app, gateway, pipeline
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  Lakeflow Ignition Connector - Quick Links"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo " Ignition Gateway"
	@echo "   $(GATEWAY_URL_83)"
	@echo "   Health:  $(GATEWAY_URL_83)/system/zerobus/health"
	@echo "   Diag:    $(GATEWAY_URL_83)/system/zerobus/diagnostics"
	@echo ""
	@echo " Zerobus Ingest (gRPC — use this host in connector / configure-83)"
	@echo "   $(ZEROBUS_ENDPOINT)"
	@echo ""
	@echo " Databricks Workspace"
	@WS_HOST=$$(awk '/^\[$(DATABRICKS_CONFIG_PROFILE)\]/{found=1} found && /^host/{gsub(/^[^=]+=[ \t]*/,""); print; exit}' ~/.databrickscfg 2>/dev/null); \
	if [ -n "$$WS_HOST" ]; then \
		echo "   https://$$WS_HOST"; \
		echo "   Catalog:   https://$$WS_HOST/explore/data/$(CATALOG)/$(SCHEMA)"; \
		APP_URL=$$(databricks apps get $(APP_NAME) -p $(DATABRICKS_CONFIG_PROFILE) 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('url',''))" 2>/dev/null); \
		if [ -n "$$APP_URL" ]; then \
			echo "   App:       $$APP_URL"; \
		else \
			echo "   Apps:      https://$$WS_HOST/apps"; \
		fi; \
		echo "   Pipelines: https://$$WS_HOST/pipelines"; \
	else \
		echo "   (could not read host from [$(DATABRICKS_CONFIG_PROFILE)] profile)"; \
	fi
	@echo ""
	@echo " Key Make commands"
	@echo "   make simulate-83      Start synthetic data"
	@echo "   make health-83        Gateway health check"
	@echo "   make diag-83          Full diagnostics"
	@echo "   make logs-83          Gateway container logs"
	@echo "   make stop-83          Stop gateway"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ──────────────────────────────────────────────────────────────
# Convenience combos
# ──────────────────────────────────────────────────────────────

.PHONY: all-83
all-83: build-83 up-83 ## Build + start 8.3 (still need setup wizard + configure)

.PHONY: all-81
all-81: build-81 up-81 ## Build + start 8.1 (still need configure)

.PHONY: db-all
db-all: db-create-sp db-setup-sql db-wheel db-recreate-pipeline db-deploy db-grant-app-sp db-lakebase-post-deploy db-run ## Full Databricks setup (SP + SQL + wheel + pipeline recreate + bundle deploy + Lakebase DDL + run)

.PHONY: bootstrap-83
bootstrap-83: db-all build-83 up-83 ## Everything from scratch (steps 1-4, then manual 4b-8)
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  Lakeflow Ignition Connector - Bootstrap complete"
	@echo ""
	@echo "  Your Ignition-to-Databricks pipeline is provisioned and ready."
	@echo "  OT tag data will stream directly into Delta Lake - no Kafka, no ETL jobs."
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  What was deployed (Steps 1-4):"
	@echo ""
	@echo "    ✔ Service principal '$(SP_NAME)' (profile: $(SP_PROFILE_NAME))"
	@echo "    ✔ Unity Catalog:  $(CATALOG).$(SCHEMA) + raw_tags table + UC functions"
	@echo "    ✔ Databricks App, SDP pipeline, Lakebase instance, training job"
	@echo "    ✔ Ignition module built with Zerobus connector"
	@echo "    ✔ Gateway running at $(GATEWAY_URL_83)"
	@echo ""
	@echo "  Continue with (run in this order):"
	@echo ""
	@echo "    4b  make setup-wizard-83       Complete Ignition setup in browser"
	@echo "    5   make configure-83          Push SP credentials to gateway"
	@echo "    6   make simulate-83           Start synthetic data generation"
	@echo "    7   make links-83              Show all URLs"
	@echo "    8   make db-train-health-model (optional) Run training job"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

.PHONY: nuke-83
nuke-83: db-nuke clean-83 bootstrap-83 ## Hard nuke Databricks + gateway, then rebuild

.PHONY: next-steps-83
next-steps-83: ## Print post-bootstrap steps (4b-8) in sequence
	@echo ""
	@echo " Continue with (run in this order):"
	@echo "   4b  make setup-wizard-83       Complete Ignition setup in browser"
	@echo "   5   make configure-83          Push SP credentials to gateway"
	@echo "   6   make simulate-83           Start synthetic data generation"
	@echo "   7   make links-83              Show all URLs"
	@echo "   8   make db-train-health-model (optional) Run training job"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""

.PHONY: redeploy
redeploy: ## Print steps to redeploy to a new workspace (see CLAUDE.md)
	@echo "Redeploy to a new workspace:"
	@echo "  1. In ~/.databrickscfg set [$(DATABRICKS_CONFIG_PROFILE)] host = new workspace URL"
	@echo "  2. Create SQL warehouse in new workspace; note the ID"
	@echo "  3. Run:"
	@echo "     make db-create-sp"
	@echo "     DATABRICKS_WAREHOUSE_ID=<id> make db-setup-sql"
	@echo "     make db-wheel"
	@echo "     make db-deploy"
	@echo "     make db-lakebase-post-deploy"
	@echo "     make db-run"
	@echo "     make build-83 up-83"
	@echo "  4. Then: make setup-wizard-83 configure-83 simulate-83 links-83"
	@echo "  Set WORKSPACE_ID, DATABRICKS_REGION in .env"

# ──────────────────────────────────────────────────────────────
# Azure Container Apps (ACA)
# ──────────────────────────────────────────────────────────────

.PHONY: aca-bootstrap
aca-bootstrap: ## Provision ACR + ACA environment + gateway + simulator from scratch
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  ACA Bootstrap — full provisioning"
	@echo "  RG:       $(ACA_RG)"
	@echo "  Location: $(ACA_LOCATION)"
	@echo "  ACR:      $(ACR_NAME)"
	@echo "  Allowed:  $(ACA_ALLOWED_IP)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "▸ [1/6] Creating ACR ($(ACR_NAME))..."
	@if az acr show -n $(ACR_NAME) -g $(ACA_RG) >/dev/null 2>&1; then \
		echo "  ACR already exists — skipping"; \
	else \
		az acr create -n $(ACR_NAME) -g $(ACA_RG) --sku Basic --admin-enabled true \
			-l $(ACA_LOCATION) -o none 2>&1; \
		echo "  ✔ ACR created"; \
	fi
	@echo ""
	@echo "▸ [2/6] Building gateway image..."
	@cd $(RELEASES_DIR) && \
		az acr build -r $(ACR_NAME) -t ignition-zerobus:8.3.3 \
			--platform linux/amd64 \
			-f ../docker/ignition-gateway/Dockerfile.aci . 2>&1 | tail -3
	@echo ""
	@echo "▸ [3/6] Building simulator image..."
	@cd examples/agl_fleet && \
		az acr build -r $(ACR_NAME) -t agl-sim:latest \
			--platform linux/amd64 \
			-f Dockerfile . 2>&1 | tail -3
	@echo ""
	@echo "▸ [4/6] Creating ACA environment ($(ACA_ENV))..."
	@if az containerapp env show -n $(ACA_ENV) -g $(ACA_RG) >/dev/null 2>&1; then \
		echo "  Environment already exists — skipping"; \
	else \
		az containerapp env create --name $(ACA_ENV) -g $(ACA_RG) \
			-l $(ACA_LOCATION) -o none 2>&1; \
		echo "  ✔ Environment created"; \
	fi
	@echo ""
	@echo "▸ [5/6] Deploying Ignition gateway..."
	@ACR_PWD=$$(az acr credential show -n $(ACR_NAME) --query "passwords[0].value" -o tsv); \
	if az containerapp show -n $(ACA_GATEWAY_APP) -g $(ACA_RG) >/dev/null 2>&1; then \
		echo "  Gateway app exists — updating image"; \
		az containerapp update -n $(ACA_GATEWAY_APP) -g $(ACA_RG) \
			--image $(ACA_GATEWAY_IMAGE) \
			--query "{fqdn:properties.configuration.ingress.fqdn}" -o json 2>&1; \
	else \
		az containerapp create \
			--name $(ACA_GATEWAY_APP) -g $(ACA_RG) --environment $(ACA_ENV) \
			--image $(ACA_GATEWAY_IMAGE) \
			--registry-server $(ACR_NAME).azurecr.io \
			--registry-username $(ACR_NAME) --registry-password "$$ACR_PWD" \
			--target-port 8088 --ingress external --transport http \
			--min-replicas 1 --max-replicas 1 --cpu 2 --memory 4Gi \
			--env-vars ACCEPT_IGNITION_EULA=Y \
			--query "{fqdn:properties.configuration.ingress.fqdn}" -o json 2>&1; \
	fi
	@echo ""
	@echo "▸ Adding IP restriction ($(ACA_ALLOWED_IP))..."
	@az containerapp ingress access-restriction set \
		--name $(ACA_GATEWAY_APP) -g $(ACA_RG) \
		--rule-name allow-operator --action Allow \
		--ip-address $(ACA_ALLOWED_IP)/32 \
		--description "Operator VPN/IP" -o none 2>&1
	@echo "  ✔ Only $(ACA_ALLOWED_IP) can reach the gateway"
	@echo ""
	@ACA_GW_FQDN=$$(az containerapp show -n $(ACA_GATEWAY_APP) -g $(ACA_RG) \
		--query "properties.configuration.ingress.fqdn" -o tsv); \
	echo "▸ [6/6] Deploying simulator..."; \
	ACA_INTERNAL_URL="https://$$(echo $$ACA_GW_FQDN | sed 's/\.\(.*\)/.internal.\1/')"; \
	ACR_PWD=$$(az acr credential show -n $(ACR_NAME) --query "passwords[0].value" -o tsv); \
	if az containerapp show -n $(ACA_SIM_APP) -g $(ACA_RG) >/dev/null 2>&1; then \
		echo "  Simulator app exists — updating"; \
		az containerapp update -n $(ACA_SIM_APP) -g $(ACA_RG) \
			--image $(ACA_SIM_IMAGE) \
			--set-env-vars \
				IGNITION_GATEWAY_URL=$$ACA_INTERNAL_URL \
				SIM_SITES=$(SIM_SITES) SIM_UNITS=$(SIM_UNITS) \
				SIM_INTERVAL_MS=$(SIM_INTERVAL) SIM_TICKS=$(SIM_TICKS) \
				PYTHONUNBUFFERED=1 \
			-o none 2>&1; \
	else \
		az containerapp create \
			--name $(ACA_SIM_APP) -g $(ACA_RG) --environment $(ACA_ENV) \
			--image $(ACA_SIM_IMAGE) \
			--registry-server $(ACR_NAME).azurecr.io \
			--registry-username $(ACR_NAME) --registry-password "$$ACR_PWD" \
			--min-replicas 0 --max-replicas 1 --cpu 0.5 --memory 1Gi \
			--env-vars \
				IGNITION_GATEWAY_URL=$$ACA_INTERNAL_URL \
				SIM_SITES=$(SIM_SITES) SIM_UNITS=$(SIM_UNITS) \
				SIM_INTERVAL_MS=$(SIM_INTERVAL) SIM_TICKS=$(SIM_TICKS) \
				PYTHONUNBUFFERED=1 \
			-o none 2>&1; \
	fi
	@echo "  ✔ Simulator deployed (stopped — start after setup wizard)"
	@echo ""
	@ACA_GW_FQDN=$$(az containerapp show -n $(ACA_GATEWAY_APP) -g $(ACA_RG) \
		--query "properties.configuration.ingress.fqdn" -o tsv); \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo "  ✔ ACA bootstrap complete"; \
	echo ""; \
	echo "  Gateway:    https://$$ACA_GW_FQDN"; \
	echo "  Allowed IP: $(ACA_ALLOWED_IP)"; \
	echo ""; \
	echo "  Next steps:"; \
	echo "    1. make aca-setup-wizard   (complete EULA + admin user in browser)"; \
	echo "    2. make aca-configure      (push Zerobus SP credentials)"; \
	echo "    3. make aca-start-sim      (start the fleet simulator)"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

.PHONY: aca-setup-wizard
aca-setup-wizard: ## Open the ACA gateway setup wizard in browser
	@ACA_GW_FQDN=$$(az containerapp show -n $(ACA_GATEWAY_APP) -g $(ACA_RG) \
		--query "properties.configuration.ingress.fqdn" -o tsv); \
	URL="https://$$ACA_GW_FQDN"; \
	echo "▸ Opening $$URL ..."; \
	echo "  Complete: EULA → admin/password → Standard Trial → Finish"; \
	open "$$URL" 2>/dev/null || xdg-open "$$URL" 2>/dev/null || echo "  Open $$URL in your browser"

.PHONY: aca-configure
aca-configure: ## Push Zerobus SP credentials to ACA gateway
	@ACA_GW_FQDN=$$(az containerapp show -n $(ACA_GATEWAY_APP) -g $(ACA_RG) \
		--query "properties.configuration.ingress.fqdn" -o tsv); \
	echo "▸ Configuring Zerobus on ACA gateway..."; \
	GATEWAY_URL_83="https://$$ACA_GW_FQDN" $(MAKE) configure-83

.PHONY: aca-build-gateway
aca-build-gateway: ## Build + push Ignition gateway image to ACR (cloud build)
	@echo "▸ Building gateway image in ACR..."
	cd $(RELEASES_DIR) && \
		az acr build -r $(ACR_NAME) \
			-t ignition-zerobus:8.3.3 \
			--platform linux/amd64 \
			-f ../docker/ignition-gateway/Dockerfile.aci . 2>&1 | tail -5
	@echo "✔ Gateway image pushed to $(ACR_NAME).azurecr.io/ignition-zerobus:8.3.3"

.PHONY: aca-build-sim
aca-build-sim: ## Build + push simulator image to ACR (cloud build)
	@echo "▸ Building simulator image in ACR..."
	cd examples/agl_fleet && \
		az acr build -r $(ACR_NAME) \
			-t agl-sim:latest \
			--platform linux/amd64 \
			-f Dockerfile . 2>&1 | tail -5
	@echo "✔ Simulator image pushed to $(ACR_NAME).azurecr.io/agl-sim:latest"

.PHONY: aca-deploy-sim
aca-deploy-sim: ## Deploy or update the simulator in ACA
	@echo "▸ Deploying simulator to ACA environment $(ACA_ENV)..."
	@ACA_GW_FQDN=$$(az containerapp show -n $(ACA_GATEWAY_APP) -g $(ACA_RG) \
		--query "properties.configuration.ingress.fqdn" -o tsv); \
	ACA_INTERNAL_URL="https://$$(echo $$ACA_GW_FQDN | sed 's/\.\(.*\)/.internal.\1/')"; \
	ACR_PWD=$$(az acr credential show -n $(ACR_NAME) --query "passwords[0].value" -o tsv); \
	echo "  Internal gateway URL: $$ACA_INTERNAL_URL"; \
	if az containerapp show -n $(ACA_SIM_APP) -g $(ACA_RG) >/dev/null 2>&1; then \
		az containerapp update -n $(ACA_SIM_APP) -g $(ACA_RG) \
			--image $(ACA_SIM_IMAGE) \
			--set-env-vars \
				IGNITION_GATEWAY_URL=$$ACA_INTERNAL_URL \
				SIM_SITES=$(SIM_SITES) SIM_UNITS=$(SIM_UNITS) \
				SIM_INTERVAL_MS=$(SIM_INTERVAL) SIM_TICKS=$(SIM_TICKS) \
				PYTHONUNBUFFERED=1 \
			--query "{revision:properties.latestRevisionName}" -o json 2>&1; \
	else \
		az containerapp create \
			--name $(ACA_SIM_APP) -g $(ACA_RG) --environment $(ACA_ENV) \
			--image $(ACA_SIM_IMAGE) \
			--registry-server $(ACR_NAME).azurecr.io \
			--registry-username $(ACR_NAME) --registry-password "$$ACR_PWD" \
			--min-replicas 1 --max-replicas 1 --cpu 0.5 --memory 1Gi \
			--env-vars \
				IGNITION_GATEWAY_URL=$$ACA_INTERNAL_URL \
				SIM_SITES=$(SIM_SITES) SIM_UNITS=$(SIM_UNITS) \
				SIM_INTERVAL_MS=$(SIM_INTERVAL) SIM_TICKS=$(SIM_TICKS) \
				PYTHONUNBUFFERED=1 \
			--query "{name:name, revision:properties.latestRevisionName}" -o json 2>&1; \
	fi
	@echo "✔ Simulator deployed. Check: make aca-logs-sim"

.PHONY: aca-stop-sim
aca-stop-sim: ## Stop the simulator (scale to 0)
	@echo "▸ Stopping simulator..."
	@az containerapp update -n $(ACA_SIM_APP) -g $(ACA_RG) \
		--min-replicas 0 --max-replicas 1 \
		--query "{replicas:properties.template.scale}" -o json 2>&1
	@echo "✔ Simulator stopped"

.PHONY: aca-start-sim
aca-start-sim: ## Start the simulator (scale to 1)
	@echo "▸ Starting simulator..."
	@az containerapp update -n $(ACA_SIM_APP) -g $(ACA_RG) \
		--min-replicas 1 --max-replicas 1 \
		--query "{replicas:properties.template.scale}" -o json 2>&1
	@echo "✔ Simulator started"

.PHONY: aca-logs-sim
aca-logs-sim: ## Tail simulator logs
	@az containerapp logs show -n $(ACA_SIM_APP) -g $(ACA_RG) --tail 50 --follow 2>&1

.PHONY: aca-logs-gateway
aca-logs-gateway: ## Tail gateway container logs
	@az containerapp logs show -n $(ACA_GATEWAY_APP) -g $(ACA_RG) --tail 50 --follow 2>&1

.PHONY: aca-status
aca-status: ## Show status of all ACA apps
	@echo "▸ ACA apps in $(ACA_ENV):"
	@az containerapp list -g $(ACA_RG) \
		--query "[].{name:name, state:properties.provisioningState, replicas:properties.template.scale.minReplicas, fqdn:properties.configuration.ingress.fqdn}" \
		-o table 2>&1
	@echo ""
	@echo "▸ Gateway diagnostics:"
	@curl -sf $(GATEWAY_URL_83)/system/zerobus/diagnostics 2>/dev/null | \
		grep -E 'Events Received|Events Sent|Queue Size|Dropped|Failures' || \
		echo "  (gateway not reachable from this machine)"

.PHONY: aca-clean
aca-clean: ## Delete all ACA resources (apps, environment, ACR)
	@echo "▸ Deleting ACA apps and environment..."
	-@az containerapp delete -n $(ACA_SIM_APP) -g $(ACA_RG) -y 2>/dev/null
	-@az containerapp delete -n $(ACA_GATEWAY_APP) -g $(ACA_RG) -y 2>/dev/null
	-@az containerapp env delete -n $(ACA_ENV) -g $(ACA_RG) -y 2>/dev/null
	-@az acr delete -n $(ACR_NAME) -g $(ACA_RG) -y 2>/dev/null
	@echo "✔ ACA resources deleted (apps, environment, ACR)"

# ──────────────────────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  Lakeflow Ignition Connector"
	@echo "  Stream OT tag data from Ignition to Databricks - no Kafka required"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  Why this matters:"
	@echo "    Industrial OT data is trapped in proprietary historians. This connector"
	@echo "    streams tag-change events directly into Delta Lake in real time - giving"
	@echo "    operations teams a unified lakehouse for analytics, ML, and dashboards"
	@echo "    without middleware, ETL jobs, or Kafka clusters to manage."
	@echo ""
	@echo "  ┌──────────────────────┐     ┌───────────────────────┐     ┌────────────────────────────┐"
	@echo "  │   IGNITION GATEWAY   │     │  ZEROBUS CONNECTOR    │     │   DATABRICKS LAKEHOUSE     │"
	@echo "  │                      │     │  (Ignition module)    │     │                            │"
	@echo "  │  OPC-UA tag changes  │     │                       │     │  ┌──────────────────────┐  │"
	@echo "  │  + exception filter  ├────>│  SDT compression      │     │  │ Bronze: raw_tags     │  │"
	@echo "  │                      │     │  protobuf encoding    ├────>│  │ (Delta + CDF)        │  │"
	@echo "  │  Timer scripts       │     │  store-and-forward    │     │  └──────────┬───────────┘  │"
	@echo "  │  Memory tags         │     │  gRPC streaming       │     │             │              │"
	@echo "  │  Simulated assets    │     │                       │     │  ┌──────────▼───────────┐  │"
	@echo "  └──────────────────────┘     │  Alt: JDBC to         │     │  │ Silver: aggregated   │  │"
	@echo "                               │  Lakebase (Postgres)  │     │  │ (SDP pipeline)       │  │"
	@echo "                               └───────────────────────┘     │  └──────────┬───────────┘  │"
	@echo "                                                             │             │              │"
	@echo "  ┌──────────────────────┐                                   │  ┌──────────▼───────────┐  │"
	@echo "  │   FLEET SIMULATOR    │     HTTP POST                     │  │ Gold: health scores  │  │"
	@echo "  │                      ├──────────────────────────────────>│  │ ML models, alerts    │  │"
	@echo "  │  BESS + Grid + CMMS  │     /system/zerobus/ingest/batch  │  └──────────┬───────────┘  │"
	@echo "  │  ~2,700 events/sec   │                                   │             │              │"
	@echo "  └──────────────────────┘                                   └─────────────┼──────────────┘"
	@echo "                                                                           │"
	@echo "                                                             ┌─────────────▼──────────────┐"
	@echo "                                                             │   DATABRICKS APP           │"
	@echo "                                                             │   Real-time OT dashboard   │"
	@echo "                                                             │   Asset health + alerts    │"
	@echo "                                                             └────────────────────────────┘"
	@echo ""
	@echo "══ From scratch (8 steps) ══════════════════"
	@echo ""
	@printf "  \033[36mmake bootstrap-83\033[0m         Steps 1-4 (automated)\n"
	@echo "    Step 1: Create SP, generate OAuth secret, assign to workspace"
	@echo "    Step 2: Create catalog/schema/tables, bundle deploy (app + pipeline + Lakebase + job)"
	@echo "    Step 3: Build Ignition + Zerobus module"
	@echo "    Step 4: Start Ignition gateway"
	@echo ""
	@printf "  \033[36mmake setup-wizard-83\033[0m      Step 4b: Accept EULA + create admin (browser)\n"
	@printf "  \033[36mmake configure-83\033[0m         Step 5:  Push SP credentials to gateway\n"
	@printf "  \033[36mmake simulate-83\033[0m          Step 6:  Start synthetic data generation\n"
	@printf "  \033[36mmake links-83\033[0m             Step 7:  Print all URLs\n"
	@printf "  \033[36mmake db-train-health-model\033[0m Step 8:  (optional) Run training job\n"
	@echo ""
	@echo "══ Full reset (clean Databricks + Ignition, then bootstrap) ══"
	@echo "  make db-clean clean-83 bootstrap-83"
	@echo "  then: make setup-wizard-83 configure-83 simulate-83 links-83"
	@echo ""
	@echo "══ Individual targets ══════════════════════"
	@echo ""
	@echo "── Gateway ─────────────────────────────────"
	@grep -E '^(build|up|start|stop|clean|logs|setup-wizard|restore|configure|configure-postgres|configure-zerobus|configure-lakebase|health|diag|test-connection|all)-[0-9]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "── Databricks ──────────────────────────────"
	@grep -E '^db-[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "── Simulator ───────────────────────────────"
	@grep -E '^simulate-[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "── Azure Container Apps (ACA) ──────────────"
	@grep -E '^aca-[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "── Links ───────────────────────────────────"
	@grep -E '^links-[0-9]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "── Overrides (or set once in .env and source before make) ──"
	@echo "  DATABRICKS_WAREHOUSE_ID=<id> WORKSPACE_ID=<id> DATABRICKS_REGION=<region>"
	@echo "  CATALOG=x SCHEMA=y make db-setup-sql"
	@echo "  SKIP_CATALOG_CREATE=1 make db-setup-sql   (if catalog exists / no CREATE CATALOG permission)"
	@echo "  Heavier sim: SIM_SITES=5 SIM_UNITS=4 SIM_INTERVAL=500 make simulate-83"
	@echo "  SP_NAME=my-sp SP_PROFILE_NAME=my-sp make db-create-sp"
