SHELL := /bin/bash

MODULE_DIR := module
DOCKER_DIR := docker/ignition-gateway

PORT_83 ?= 7088
PORT_81 ?= 8097

.PHONY: help
help: ## Show available targets
	@echo "Module build targets:"
	@echo "  make build-81            Build Ignition 8.1 module"
	@echo "  make build-83            Build Ignition 8.3 module"
	@echo "  make build-all           Build both module variants"
	@echo ""
	@echo "Docker gateway targets:"
	@echo "  make docker-up-83        Start Ignition 8.3 gateway"
	@echo "  make docker-up-83-restore Start Ignition 8.3 from restore backup"
	@echo "  make docker-down-83      Stop Ignition 8.3 gateway"
	@echo "  make docker-up-81        Start Ignition 8.1 gateway"
	@echo "  make docker-up-81-restore Start Ignition 8.1 from restore backup"
	@echo "  make docker-down-81      Stop Ignition 8.1 gateway"
	@echo ""
	@echo "Health checks:"
	@echo "  make health-83           Check 8.3 gateway StatusPing"
	@echo "  make health-81           Check 8.1 gateway StatusPing"

.PHONY: build-81
build-81: ## Build Ignition 8.1 module artifact
	@cd "$(MODULE_DIR)" && ./gradlew buildModule81

.PHONY: build-83
build-83: ## Build Ignition 8.3 module artifact
	@cd "$(MODULE_DIR)" && ./gradlew buildModule83

.PHONY: build-all
build-all: build-81 build-83 ## Build both 8.1 and 8.3 artifacts

.PHONY: docker-up-83
docker-up-83: ## Start Ignition 8.3 gateway
	@cd "$(DOCKER_DIR)" && docker compose -f docker-compose.83.yml up -d

.PHONY: docker-up-83-restore
docker-up-83-restore: ## Start Ignition 8.3 gateway from restore.gwbk
	@cd "$(DOCKER_DIR)" && docker compose -f docker-compose.83.restore.yml up -d

.PHONY: docker-down-83
docker-down-83: ## Stop Ignition 8.3 gateway
	@cd "$(DOCKER_DIR)" && docker compose -f docker-compose.83.yml down

.PHONY: docker-up-81
docker-up-81: ## Start Ignition 8.1 gateway
	@cd "$(DOCKER_DIR)" && docker compose -f docker-compose.yml up -d

.PHONY: docker-up-81-restore
docker-up-81-restore: ## Start Ignition 8.1 gateway from restore.gwbk
	@cd "$(DOCKER_DIR)" && docker compose -f docker-compose.restore.yml up -d

.PHONY: docker-down-81
docker-down-81: ## Stop Ignition 8.1 gateway
	@cd "$(DOCKER_DIR)" && docker compose -f docker-compose.yml down

.PHONY: health-83
health-83: ## Check Ignition 8.3 gateway health
	@curl -sf "http://localhost:$(PORT_83)/StatusPing" && echo

.PHONY: health-81
health-81: ## Check Ignition 8.1 gateway health
	@curl -sf "http://localhost:$(PORT_81)/StatusPing" && echo
