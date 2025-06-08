# Doris MCP Server Makefile
# Provides convenient commands using UV

.PHONY: help install sync dev test lint format build clean check start-stdio start-sse

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies using UV"
	@echo "  sync        - Sync dependencies and create virtual environment"
	@echo "  dev         - Install development dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linting tools"
	@echo "  format      - Format code with black and isort"
	@echo "  build       - Build the package"
	@echo "  clean       - Clean build artifacts"
	@echo "  check       - Run all checks (format, lint, test)"
	@echo "  start-stdio - Start server in stdio mode"
	@echo "  start-sse   - Start server in SSE mode"

# Install dependencies
install:
	uv sync

# Sync dependencies with development extras
sync:
	uv sync

# Install development dependencies
dev:
	uv sync --dev

# Run tests
test:
	uv run pytest

# Run linting tools
lint:
	uv run ruff check doris_mcp_server/
	uv run mypy doris_mcp_server/

# Format code
format:
	uv run ruff format doris_mcp_server/
	uv run ruff check --fix doris_mcp_server/

# Build the package
build:
	uv build

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +

# Run all checks
check: format lint test

# Start server in stdio mode
start-stdio:
	uv run python -m doris_mcp_server.main --transport stdio

# Start server in SSE mode
start-sse:
	uv run python -m doris_mcp_server.main --transport sse --host 0.0.0.0 --port 8080

# Start server with custom database settings
start-dev:
	uv run python -m doris_mcp_server.main \
		--transport stdio \
		--db-host localhost \
		--db-port 9030 \
		--db-user root \
		--log-level DEBUG

# Run a single test file
test-file:
	uv run pytest $(FILE) -v

# Install and run in one command
run: install start-stdio

# Development setup
setup: dev
	@echo "✅ Development environment is ready!"
	@echo "Run 'make start-stdio' to start the server"

# Add dependencies
add:
	uv add $(PACKAGE)

# Add development dependencies
add-dev:
	uv add --dev $(PACKAGE)

# Show dependency tree
deps:
	uv tree

# Lock dependencies
lock:
	uv lock

# Check for outdated dependencies
outdated:
	uv tree --outdated

# Export requirements.txt
export-requirements:
	uv export --no-hashes > requirements.txt

# Show UV version and info
info:
	uv --version
	uv python list 