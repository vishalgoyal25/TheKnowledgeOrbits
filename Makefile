# ==============================================================================
# TheKnowledgeOrbits - Project Makefile
#
# IMPORTANT: All backend commands run INSIDE Docker.
# Do NOT run `pytest`, `flake8`, `mypy`, or `black` directly from your local
# terminal — your local Anaconda env doesn't have the project dependencies.
#
# Usage:  make test
#         make lint
#         make fmt
#         make check
# ==============================================================================

BACKEND_CONTAINER = TheKnowledgeOrbits_backend

# ---- Testing ----

test:
	docker exec $(BACKEND_CONTAINER) pytest engines/ -v --tb=short

test-quick:
	docker exec $(BACKEND_CONTAINER) pytest engines/ -q

test-content:
	docker exec $(BACKEND_CONTAINER) pytest engines/content/ engines/current_affairs/ engines/knowledge/ -v --tb=short

test-ci:
	docker exec $(BACKEND_CONTAINER) pytest engines/ -x --tb=short

# ---- Build targets ----

build:
	# Fast build: no dev tools (~5-8 min). Use for daily development.
	docker-compose up -d --build

build-test:
	# Full build: includes pytest/black/mypy (~25 min first time, cached after).
	docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d --build

# ---- Linting / Formatting ----

fmt:
	docker exec $(BACKEND_CONTAINER) black engines/ conftest.py

lint:
	docker exec $(BACKEND_CONTAINER) flake8 engines/ conftest.py

type-check:
	docker exec $(BACKEND_CONTAINER) mypy engines/

# ---- Combined quality gate ----

check: fmt lint
	docker exec $(BACKEND_CONTAINER) pytest engines/ -q

# ---- Django ----

migrate:
	docker exec $(BACKEND_CONTAINER) python manage.py migrate

shell:
	docker exec -it $(BACKEND_CONTAINER) python manage.py shell

.PHONY: test test-quick test-content test-ci fmt lint type-check check migrate shell
