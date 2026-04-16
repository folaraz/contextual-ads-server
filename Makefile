DB_URL=postgresql://adsuser:adspassword@localhost:5435/contextual_ads?sslmode=disable
COUNT ?= 10000

# -----------------------------------------------------------------------------
# Database Commands
# -----------------------------------------------------------------------------
createdb:
	docker exec contextual-ads-server-postgres-1 createdb --username=adsuser contextual_ads

dropdb:
	docker exec contextual-ads-server-postgres-1 dropdb --username=adsuser contextual_ads

migrateup:
	migrate -path db/migration -database $(DB_URL) -verbose up

migratedown:
	migrate -path db/migration -database $(DB_URL) -verbose down

resetdb: dropdb createdb migrateup
	@echo "Database reset complete"

sqlc:
	sqlc generate

# Setup database from scratch (create, migrate, generate sqlc) -- idempotent
setup-db:
	@echo "Setting up database..."
	-docker exec contextual-ads-server-postgres-1 createdb --username=adsuser contextual_ads 2>/dev/null || true
	migrate -path db/migration -database $(DB_URL) -verbose up
	sqlc generate
	@echo "Database setup complete."

# -----------------------------------------------------------------------------
# Service Management - Individual Services
# -----------------------------------------------------------------------------
contextprocessorup:
	docker compose up --build --force-recreate -d page-context-processor ad-context-processor

analyticsconsumerup:
	docker compose up --build --force-recreate -d analytics-consumer

pacingup:
	docker compose up --build --force-recreate -d pacing-worker

adserverup:
	docker compose up --build --force-recreate -d ad-server

# -----------------------------------------------------------------------------
# Service Management - Bring Up All Services
# -----------------------------------------------------------------------------

# Infrastructure only (kafka, postgres, redis)
infra-up:
	docker compose up -d zookeeper kafka kafka-init kafka-ui redis postgres
	@echo "Waiting for infrastructure to be healthy..."
	@sleep 10
	@echo "Infrastructure is up."

# Observability stack (prometheus, loki, tempo, grafana, otel-collector)
observability-up:
	cd observability && docker compose up -d
	@echo "Observability stack is up. Grafana: http://localhost:3000 (admin/admin)"

# All consumers and workers
consumers-up:
	docker compose up --build -d page-context-processor ad-context-processor analytics-consumer pacing-worker
	@echo "All consumers and workers are up."

# Flink cluster
flink-up:
	docker compose up --build -d flink-jobmanager flink-taskmanager
	@echo "Flink cluster is up. UI: http://localhost:8081"

# Go ad server
server-up:
	docker compose up --build -d ad-server
	@echo "Ad server is up. API: http://localhost:8090"

# Start everything
up: infra-up observability-up
	@echo "Waiting for observability stack..."
	@sleep 5
	$(MAKE) setup-db
	$(MAKE) consumers-up
	$(MAKE) flink-up
	$(MAKE) server-up
	@echo ""
	@echo "All services are up."
	@echo "Ad Server:    http://localhost:8090"
	@echo "Kafka UI:     http://localhost:8080"
	@echo "Flink UI:     http://localhost:8081"
	@echo "Grafana:      http://localhost:3000 (admin/admin)"
	@echo "Prometheus:   http://localhost:9090"

# Restart everything -- non-destructive, keeps data
restart: down up

# Restart everything -- destructive, drops DB, removes volumes, fresh setup
restart-clean: down-clean up

# Stop everything (observability first -- it uses contextual-ads-server_default as external network)
down:
	cd observability && docker compose down --remove-orphans
	docker compose down --remove-orphans
	@echo "All services stopped"

# Drop DB, stop everything, and remove volumes
down-clean:
	-docker exec contextual-ads-server-postgres-1 dropdb --username=adsuser contextual_ads 2>/dev/null || true
	cd observability && docker compose down -v --remove-orphans
	docker compose down -v --remove-orphans
	@echo "All services stopped, database dropped, and volumes removed"

# View logs
logs:
	docker compose logs -f

logs-server:
	docker compose logs -f ad-server

logs-consumers:
	docker compose logs -f page-context-processor ad-context-processor analytics-consumer pacing-worker

# -----------------------------------------------------------------------------
# Development - Run locally (outside docker)
# -----------------------------------------------------------------------------
run-server:
	OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317 go run ./cmd/api

# -----------------------------------------------------------------------------
# Bootstrap -- One-command setup for traffic simulation
# -----------------------------------------------------------------------------

generate-data:
	@echo "Generating campaign data ($(COUNT) campaigns)..."
	cd python && python3 scripts/bulk_ads_generator.py --count $(COUNT) --format both --no-stats
	@echo ""
	@echo "Data generated:"
	@ls -lh data/campaign_requests_*.json data/advertisers_list.json data/ads_inventory.json 2>/dev/null || true

seed-from-file:
	@echo "Seeding database from generated data..."
	@CAMPAIGN_FILE=$$(ls -t data/campaign_requests_*.json 2>/dev/null | head -1); \
	if [ -z "$$CAMPAIGN_FILE" ]; then \
		echo "Error: No campaign_requests file found. Run 'make generate-data' first."; \
		exit 1; \
	fi; \
	echo "Using: $$CAMPAIGN_FILE"; \
	go run ./tests/cmd/seed --from-file=$$CAMPAIGN_FILE --workers=10 --verbose

preprocess:
	@echo "Running NLP preprocessing (pages + ads -> Redis + PG)..."
	cd python && python3 scripts/preprocess_all.py --fast --workers 4
	@echo ""
	@echo "Pre-processed URLs written to data/preprocessed_urls.txt"

preprocess-verify:
	cd python && python3 scripts/preprocess_all.py --verify-only

# Re-populate Redis cache from PostgreSQL without re-running NLP processing
warm-cache:
	@echo "  Warming Redis cache from PostgreSQL..."
	cd python && python3 scripts/preprocess_all.py --force-recache
	@echo "  Done."

bootstrap: generate-data seed-from-file preprocess
	@echo ""
	@echo "Bootstrap complete."
	@echo ""
	@echo "  Run traffic simulation:"
	@echo "    make simulate            (1k requests, 10 workers)"
	@echo "    make simulate-heavy      (10k requests, 50 workers)"
	@echo ""
	@echo "  Run evaluations:"
	@echo "    make eval                (all evals)"
	@echo "    make eval-relevance      (relevance only)"
	@echo "    make eval-pacing         (pacing only)"

# Bootstrap with a clean database (destructive -- drops existing data)
bootstrap-clean: resetdb bootstrap

# -----------------------------------------------------------------------------
# Evaluation -- Data Generation & Test Targets
# -----------------------------------------------------------------------------

eval-data: generate-data eval-fixtures
	@echo ""
	@echo "Evaluation data ready. Run:"
	@echo "   make eval              # all evaluations"
	@echo "   make eval-relevance    # relevance only"
	@echo "   make eval-pacing       # pacing only"
	@echo "   make eval-nlp          # NLP-based (needs Python models)"

eval-fixtures:
	@echo "Generating NLP evaluation fixtures (this may take a few minutes)..."
	cd python && python3 scripts/generate_eval_fixtures.py --fast
	@echo "Fixtures generated in data/eval/"

# Run all evaluation tests
eval:
	go test ./tests/evaluation/... -v -timeout 10m

eval-relevance:
	go test ./tests/evaluation/relevance/ -v -timeout 5m

eval-pacing:
	go test ./tests/evaluation/pacing/ -v -timeout 5m

eval-short:
	go test ./tests/evaluation/relevance/ -v -timeout 3m -short

# NLP-based evaluation (requires pre-computed NLP fixtures)
eval-nlp: eval-fixtures
	@echo "Running NLP-based evaluation..."
	go test ./tests/evaluation/relevance/ -v -tags nlp_eval -run "WithRealEmbeddings|EmbeddingClustering" -timeout 5m

# -----------------------------------------------------------------------------
# E2E Test Seeding -- Legacy / Fine-Grained Targets
# -----------------------------------------------------------------------------

seed:
	go run ./tests/cmd/seed --all --verbose

seed-clean: resetdb seed
	@echo "Database reset and seeding complete"

seed-advertisers:
	go run ./tests/cmd/seed --advertisers --verbose

seed-publishers:
	go run ./tests/cmd/seed --publishers --verbose

seed-campaigns:
	go run ./tests/cmd/seed --campaigns --verbose

seed-dry-run:
	go run ./tests/cmd/seed --all --dry-run --verbose

# -----------------------------------------------------------------------------
# Traffic Simulation
# -----------------------------------------------------------------------------

# Run simulation using pre-processed page URLs
simulate:
	go run ./tests/cmd/traffic_simulator -requests 1000 -concurrency 10 -page-urls-file data/preprocessed_urls.txt

simulate-heavy:
	go run ./tests/cmd/traffic_simulator -requests 10000 -concurrency 50 -rate 500 -page-urls-file data/preprocessed_urls.txt

# Duration-based: run for 6 hours with 50 workers
simulate-soak:
	go run ./tests/cmd/traffic_simulator -duration 6h -concurrency 50 -impression-rate 0.95 -click-rate 0.06 -page-urls-file data/preprocessed_urls.txt

# -----------------------------------------------------------------------------
# One-Time / Utility Scripts
# -----------------------------------------------------------------------------

# Generate ads_inventory.json only (inventory format for eval tests)
generate-ads:
	@echo "Generating ads_inventory.json "
	cd python && python3 scripts/bulk_ads_generator.py --count 2000 --format inventory --no-stats
	@echo "Done."

generate-creatives:
	@echo "Generating creative bank via Claude API..."
	@echo "  Requires: export ANTHROPIC_API_KEY=sk-ant-..."
	cd python && python3 scripts/generate_creative_bank.py
	@echo "Done. Output: data/creative_bank.json"

# -----------------------------------------------------------------------------
# Business Metrics Dashboard
# -----------------------------------------------------------------------------
dashboard:
	cd python && streamlit run dashboard/app.py

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------
help:
	@echo ""
	@echo "Contextual Ads Server - Makefile Commands"
	@echo "=========================================="
	@echo ""
	@echo "  QUICK START (full simulation from scratch):"
	@echo "     make up                  # Start all infrastructure"
	@echo "     make bootstrap           # Generate data -> seed DB -> preprocess"
	@echo "     make simulate            # Run traffic simulation"
	@echo ""
	@echo "  EVALUATION (no infra needed for most):"
	@echo "     make eval-data           # Generate all eval datasets"
	@echo "     make eval                # Run all evaluation tests"
	@echo "     make eval-relevance      # Relevance tests only"
	@echo "     make eval-pacing         # Pacing tests only"
	@echo "     make eval-nlp            # NLP eval (needs Python models)"
	@echo ""
	@echo "  INDIVIDUAL STEPS:"
	@echo "     make generate-data       # Generate campaign + inventory JSONs"
	@echo "     make seed-from-file      # Seed DB from generated JSON"
	@echo "     make preprocess          # NLP preprocess pages + ads"
	@echo ""
	@echo "  INFRASTRUCTURE:"
	@echo "     make up                  # Start everything"
	@echo "     make down                # Stop everything"
	@echo "     make restart-clean       # Full reset + restart"
	@echo ""

.PHONY: createdb dropdb migrateup migratedown sqlc setup-db contextprocessorup analyticsconsumerup pacingup adserverup \
	resetdb seed seed-clean seed-advertisers seed-publishers seed-campaigns seed-dry-run \
	infra-up observability-up consumers-up flink-up server-up up restart restart-clean down down-clean \
	logs logs-server logs-consumers run-server \
	generate-data seed-from-file preprocess preprocess-verify bootstrap bootstrap-clean \
	eval-data eval-fixtures eval eval-relevance eval-pacing eval-short eval-nlp \
	generate-ads generate-creatives \
	simulate simulate-heavy simulate-soak \
	dashboard help
