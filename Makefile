# Makefile for ECommerceManagerAPI with Cache System

.PHONY: help build up down logs restart clean test install dev prod cache-stats cache-clear

# Default target
help:
	@echo "ECommerceManagerAPI - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev         - Start development environment"
	@echo "  install     - Install dependencies"
	@echo "  test        - Run tests"
	@echo ""
	@echo "Docker:"
	@echo "  build       - Build Docker images"
	@echo "  up          - Start all services"
	@echo "  down        - Stop all services"
	@echo "  logs        - Show logs"
	@echo "  restart     - Restart services"
	@echo ""
	@echo "Cache Management:"
	@echo "  cache-stats - Show cache statistics"
	@echo "  cache-clear - Clear all cache"
	@echo "  cache-warm  - Warm up cache"
	@echo ""
	@echo "Production:"
	@echo "  prod        - Start production environment"
	@echo "  clean       - Clean up Docker resources"

# Development
dev: install
	@echo "Starting development environment..."
	@cp env.example .env
	@echo "Please edit .env file with your configuration"
	@docker-compose -f docker-compose.dev.yml up -d

install:
	@echo "Installing dependencies..."
	@pip install -r requirements.txt

test:
	@echo "Running tests..."
	@pytest test/ -v --cov=src --cov-report=html

# Docker commands
build:
	@echo "Building Docker images..."
	@docker-compose build

up:
	@echo "Starting all services..."
	@docker-compose up -d

down:
	@echo "Stopping all services..."
	@docker-compose down

logs:
	@echo "Showing logs..."
	@docker-compose logs -f

restart:
	@echo "Restarting services..."
	@docker-compose restart

# Cache management
cache-stats:
	@echo "Cache Statistics:"
	@curl -s http://localhost:8000/health/cache | jq '.'

cache-clear:
	@echo "Clearing all cache..."
	@curl -X POST http://localhost:8000/api/v1/cache/reset

cache-warm:
	@echo "Warming up cache..."
	@python scripts/warm_cache.py

# Production
prod:
	@echo "Starting production environment..."
	@docker-compose -f docker-compose.prod.yml up -d

clean:
	@echo "Cleaning up Docker resources..."
	@docker-compose down -v
	@docker system prune -f

# Database operations
db-migrate:
	@echo "Running database migrations..."
	@alembic upgrade head

db-seed:
	@echo "Seeding database..."
	@python scripts/create_fixtures.py

# Monitoring
monitor:
	@echo "Opening monitoring dashboards..."
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Redis Commander: http://localhost:8081 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"

# Cache debugging
cache-debug:
	@echo "Cache Debug Information:"
	@echo "Redis Info:"
	@docker exec ecommerce_redis redis-cli info memory
	@echo ""
	@echo "Cache Keys:"
	@docker exec ecommerce_redis redis-cli keys "*" | head -20

# Performance testing
perf-test:
	@echo "Running performance tests..."
	@python scripts/performance_test.py

# Security
security-check:
	@echo "Running security checks..."
	@bandit -r src/
	@safety check

# Linting
lint:
	@echo "Running linters..."
	@flake8 src/
	@black --check src/
	@isort --check-only src/

format:
	@echo "Formatting code..."
	@black src/
	@isort src/
