COMPOSE ?= docker compose
COMPOSE_FILES := -f infra/docker-compose.yml
COMPOSE_DEV_FILES := -f infra/docker-compose.yml -f infra/docker-compose.dev.yml

.PHONY: dev down build logs ps test migrate

dev:
	$(COMPOSE) $(COMPOSE_DEV_FILES) up --build

down:
	$(COMPOSE) $(COMPOSE_FILES) down

build:
	$(COMPOSE) $(COMPOSE_FILES) build

logs:
	$(COMPOSE) $(COMPOSE_FILES) logs -f

ps:
	$(COMPOSE) $(COMPOSE_FILES) ps

test:
	cd go && go test ./...
	cd python && python3 -m pytest tests/ -q 2>/dev/null || (cd python && . .venv/bin/activate 2>/dev/null && pytest tests/ -q)

migrate:
	./scripts/run_migrations.sh
