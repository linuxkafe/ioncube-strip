# ioncube-strip Makefile
# Provides common development tasks

.PHONY: help install test lint format check clean

# Default target
help:
	@echo "ioncube-strip — Available targets:"
	@echo "  install     Install Python dependencies"
	@echo "  test        Run unit tests"
	@echo "  lint        Run all linters"
	@echo "  format      Format Python code with ruff"
	@echo "  check       Run all quality gates (lint + test)"
	@echo "  clean       Remove build artifacts"

# Install dependencies
install:
	pip install -r requirements.txt

# Run unit tests (no PHP 5.6 / arm56 required)
test:
	python3 -m pytest tests/unit -v

# Run integration tests (requires PHP 5.6 + arm56)
test-integration:
	@echo "Integration tests require PHP 5.6 + arm56 toolchain"
	@echo "Set PHP56, PHP56_INI, ARM56_SO environment variables"
	python3 -m pytest tests/integration -v

# Lint all code
lint:
	python3 -m ruff check lib/ tests/
	@which shellcheck >/dev/null && shellcheck bin/ioncube-strip || echo "shellcheck not installed, skipping"
	php -l lib/dump_one.php

# Format Python code
format:
	python3 -m ruff format lib/ tests/

# Full quality gate check
check: lint test
	@echo "All checks passed"

# Validate config schema
validate-config:
	python3 scripts/validate_config.py

# Check for hardcoded paths
check-hardcoded-paths:
	@echo "Checking for hardcoded paths..."
	@! grep -r "/home/" lib/ bin/ config/ --include="*.py" --include="*.sh" --include="*.php" | grep -v ".example" | grep -v "test" || (echo "FAIL: Found hardcoded /home/ paths" && exit 1)
	@! grep -r "whmcs" lib/ bin/ config/ --include="*.py" --include="*.sh" --include="*.php" | grep -v ".example" | grep -v "test" || (echo "FAIL: Found WHMCS references" && exit 1)
	@! grep -r "/tmp/arm56" lib/ bin/ config/ --include="*.py" --include="*.sh" --include="*.php" | grep -v ".example" | grep -v "test" || (echo "FAIL: Found hardcoded /tmp/arm56" && exit 1)
	@echo "No hardcoded paths found"

# Check for network calls
check-network-calls:
	@echo "Checking for network calls..."
	@! grep -r -E "(http|https)://" lib/ bin/ config/ --include="*.py" --include="*.sh" --include="*.php" || (echo "FAIL: Found URLs" && exit 1)
	@! grep -r -E "(curl|wget|requests|urllib|httpx|aiohttp)" lib/ bin/ config/ --include="*.py" --include="*.sh" --include="*.php" || (echo "FAIL: Found network libraries" && exit 1)
	@echo "No network calls found"

# Check for emojis
check-emoji:
	@echo "Checking for emojis..."
	@! grep -r -P "[\xF0-\xF4][\x80-\xBF]{3}" lib/ bin/ tests/ config/ --include="*.py" --include="*.sh" --include="*.php" --include="*.md" || (echo "FAIL: Found emojis" && exit 1)
	@echo "No emojis found"

# Check legal headers
check-legal-headers:
	@echo "Checking SPDX headers..."
	@for f in lib/*.py lib/*.php bin/*; do \
		head -10 "$$f" | grep -q "SPDX-License-Identifier" || (echo "FAIL: Missing SPDX header in $$f" && exit 1); \
	done
	@echo "All files have SPDX headers"

# Clean build artifacts
clean:
	rm -rf __pycache__ lib/__pycache__ tests/__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf dist build *.egg-info

# Install CLI globally (requires sudo)
install-cli:
	sudo cp bin/ioncube-strip /usr/local/bin/ioncube-strip
	sudo chmod +x /usr/local/bin/ioncube-strip

# Create release tarball
release: check
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'\"' -f2); \
	tar -czf "ioncube-strip-$${version}.tar.gz" \
		--exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
		--exclude='.pytest_cache' --exclude='.ruff_cache' \
		--exclude='tests/fixtures/dumps' \
		--exclude='aes' --exclude='.aes' \
		.
	@echo "Created ioncube-strip-$${version}.tar.gz"

# Verify release tarball
verify-release:
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'\"' -f2); \
	tar -tzf "ioncube-strip-$${version}.tar.gz" | head -20