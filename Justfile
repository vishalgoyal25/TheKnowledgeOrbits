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
test:
    cd backend && pytest

# Testing - Run with coverage
test-cov:
    cd backend && pytest --cov=engines --cov-report=html

# Database - Create migrations
makemigrations engine="":
    cd backend && python manage.py makemigrations {{engine}}

# Database - Run migrations
migrate:
    cd backend && python manage.py migrate

# Database - Reset database (DANGER!)
db-reset:
    cd backend && python manage.py flush --no-input

# Linting - Run black formatter
format:
    cd backend && black .

# Linting - Run flake8
lint:
    cd backend && flake8 .

# Security - Run bandit security scan
security:
    cd backend && bandit -r engines/ core/ shared/

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
