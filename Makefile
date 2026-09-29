# SRAF local stack.
#
#   make            show this help
#   make up         start the triplestore and wait until it answers
#   make ontology   fetch the current RDIP release and reload the schema graph
#   make test       run the schema-facing test suites
#   make status     what is running, which ontology version is loaded
#
# The triplestore's data lives in ./triplestore (a bind mount), not inside the
# container, so removing and recreating the container never loses anything.

PYTHON ?= python3
CONTAINER := sraf-oxigraph
ENDPOINT := http://localhost:7878

.DEFAULT_GOAL := help
.PHONY: help up down restart wait ontology ontology-force test status shell dashboard logs nuke

help:
	@sed -n '2,11p' $(MAKEFILE_LIST) | sed 's/^# \{0,1\}//'

up:
	@if [ "$$(docker inspect -f '{{.State.Running}}' $(CONTAINER) 2>/dev/null)" = "true" ]; then \
	  echo "$(CONTAINER) already running"; \
	else \
	  if docker inspect $(CONTAINER) >/dev/null 2>&1; then \
	    echo "removing stale $(CONTAINER) (data is in ./triplestore, not the container)"; \
	    docker rm -f $(CONTAINER) >/dev/null; \
	  fi; \
	  docker compose up -d oxigraph; \
	fi
	@$(MAKE) --no-print-directory wait

wait:
	@printf "waiting for oxigraph "
	@for i in $$(seq 1 30); do \
	  if curl -fsS "$(ENDPOINT)/query?query=ASK%7B%7D" \
	       -H "Accept: application/sparql-results+json" >/dev/null 2>&1; then \
	    echo "ready"; exit 0; \
	  fi; \
	  printf "."; sleep 1; \
	done; \
	echo " TIMEOUT"; \
	echo "  check: docker compose logs oxigraph"; \
	exit 1

down:
	docker compose down

restart: down up

# Fetch whatever https://w3id.org/rdip/ currently resolves to and reload the
# schema graph if it differs from the cache. Safe to run repeatedly.
ontology: up
	@$(PYTHON) -c "import ontology_loader as o, json; print(json.dumps(o.ensure_latest(), indent=2))"

# Reload even when the checksum is unchanged.
ontology-force: up
	@$(PYTHON) -c "import ontology_loader as o, json; print(json.dumps(o.ensure_latest(force=True), indent=2))"

test:
	$(PYTHON) -m pytest tests/test_shacl_shapes.py tests/test_mapper.py \
	                    tests/test_conflict_queries.py -q

status:
	@echo "== containers =="
	@docker compose ps || true
	@echo
	@echo "== ontology cache =="
	@cat .ontology_cache/meta.json 2>/dev/null || echo "(no cache yet, run: make ontology)"
	@echo
	@echo "== loaded schema graph =="
	@$(PYTHON) -c "import ontology_loader as o; from triplestore_client import count_triples; \
	print(count_triples(o.SCHEMA_GRAPH), 'triples in', o.SCHEMA_GRAPH)" \
	  2>/dev/null || echo "(triplestore unreachable, run: make up)"
	@echo
	@echo "== recipe terms present =="
	@grep -c ExecutionRecipe .ontology_cache/rdip.ttl 2>/dev/null \
	  | sed 's/^0$$/0  <-- cache predates v2.1.0, run: make ontology/' \
	  || echo "(no cache)"

shell: up
	docker compose up -d sraf-engine
	docker compose exec sraf-engine bash

dashboard: up
	docker compose --profile dashboard up -d dashboard
	@echo "dashboard: http://localhost:8501"

logs:
	docker compose logs -f oxigraph

# Remove the container only. ./triplestore is untouched.
nuke:
	-docker rm -f $(CONTAINER)
