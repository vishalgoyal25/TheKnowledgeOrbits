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
#         make check-all (pre-commit equivalent)
# ==============================================================================

BACKEND_CONTAINER = TheKnowledgeOrbits_backend

# ---- Testing ----

test-backend:
	docker exec $(BACKEND_CONTAINER) pytest engines/ -v --tb=short

test-quick:
	docker exec $(BACKEND_CONTAINER) pytest engines/ -q

test-content:
	docker exec $(BACKEND_CONTAINER) pytest engines/content/ engines/current_affairs/ engines/knowledge/ -v --tb=short

test-ci:
	docker exec $(BACKEND_CONTAINER) pytest engines/ -x --tb=short

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

# ---- Build targets ----

build:
	# Fast build: no dev tools (~5-8 min). Use for daily development.
	docker-compose up -d --build

build-test:
	# Full build: includes pytest/black/mypy (~25 min first time, cached after).
	docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d --build

# ---- Linting / Formatting ----

fmt-backend:
	docker exec $(BACKEND_CONTAINER) isort engines/ conftest.py && docker exec $(BACKEND_CONTAINER) black engines/ conftest.py

fmt-frontend:
	cd frontend && npm run format

fmt: fmt-backend fmt-frontend

lint-backend:
	docker exec $(BACKEND_CONTAINER) flake8 engines/ conftest.py

lint-frontend:
	cd frontend && npm run lint

lint: lint-backend lint-frontend

type-check-backend:
	docker exec $(BACKEND_CONTAINER) mypy engines/

type-check-frontend:
	cd frontend && npm run type-check

type-check: type-check-backend type-check-frontend

# ---- Combined quality gate ----

check: fmt lint
	docker exec $(BACKEND_CONTAINER) pytest engines/ -q

check-all:
	pre-commit run --all-files

# ---- Deep Check (Pre-Push Layer) ----
deepcheck:
	@echo "Running Backend Checks (via Docker)..."
	-docker exec $(BACKEND_CONTAINER) mypy engines/
	-docker exec $(BACKEND_CONTAINER) pytest engines/ -q
	@echo "Running Frontend Checks..."
	cd frontend && npm run type-check && npm test

# ---- Django ----

migrate:
	docker exec $(BACKEND_CONTAINER) python manage.py migrate

shell:
	docker exec -it $(BACKEND_CONTAINER) python manage.py shell

.PHONY: test-backend test-frontend test test-quick test-content test-ci fmt-backend fmt-frontend fmt lint-backend lint-frontend lint type-check-backend type-check-frontend type-check check check-all deepcheck migrate shell
