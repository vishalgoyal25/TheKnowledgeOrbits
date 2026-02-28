# Justfile - Command runner for TheKnowledgeOrbits

# Default recipe (shows help)
default:
    @just --list

# Development - Run backend server
dev-backend:
    cd backend && python manage.py runserver

# Development - Run frontend server
dev-frontend:
    cd frontend && npm run dev

# Development - Run both (requires separate terminals)
dev:
    @echo "Run 'just dev-backend' in one terminal"
    @echo "Run 'just dev-frontend' in another terminal"

# Testing - Run backend tests
test-backend:
    cd backend && pytest

# Testing - Run frontend tests
test-frontend:
    cd frontend && npm test

# Testing - Run with coverage
test-cov:
    cd backend && pytest --cov=engines --cov-report=html

# Type Checking - Backend
typecheck-backend:
    cd backend && mypy .

# Type Checking - Frontend
typecheck-frontend:
    cd frontend && npm run type-check

# Database - Create migrations
makemigrations engine="":
    cd backend && python manage.py makemigrations {{engine}}

# Database - Run migrations
migrate:
    cd backend && python manage.py migrate

# Database - Reset database (DANGER!)
db-reset:
    cd backend && python manage.py flush --no-input

# Formatting - Run black and isort (Backend)
format-backend:
    cd backend && isort . && black .

# Formatting - Run prettier (Frontend)
format-frontend:
    cd frontend && npm run format

# Linting - Run flake8 (Backend)
lint-backend:
    cd backend && flake8 .

# Linting - Run eslint (Frontend)
lint-frontend:
    cd frontend && npm run lint

# Security - Run bandit security scan
security:
    cd backend && bandit -r engines/ core/ -x "*/tests/*"

# Shell - Django shell
shell:
    cd backend && python manage.py shell

# Docker - Start all services
docker-up:
    docker-compose up -d

# Docker - Stop all services
docker-down:
    docker-compose down

# Docker - View logs
docker-logs:
    docker-compose logs -f

# Setup - Install backend dependencies
install-backend:
    cd backend && pip install -r requirements.txt

# Setup - Install frontend dependencies
install-frontend:
    cd frontend && npm install

# Setup - Full install
install: install-backend install-frontend

# Pre-commit - Run all checks
precommit:
    pre-commit run --all-files
