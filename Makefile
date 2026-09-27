# ioncube-strip Makefile
# Provides common development tasks

.PHONY: help install test test-integration lint format check clean manifest symbols

# Default target
help:
	@echo "ioncube-strip — Available targets:"
	@echo "  install     Install Python dependencies"
	@echo "  manifest    Reflection class manifests  (FILES=... OUTPUT=...)"
	@echo "  symbols     arm56 symbol dumps         (FILES=... OUTPUT=...)"
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
	python3 -m ruff check lib/ tests/ scripts/
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck bin/ioncube-strip; \
	else \
		echo "shellcheck not installed, skipping"; \
	fi
	php -l lib/dump_one.php

# Format Python code
format:
	python3 -m ruff format lib/ tests/ scripts/

# Full quality gate.
#
# Every policy target is reachable from here. `release` and `verify-release`
# were both broken for the life of the project -- `cut -d'\"'` passed a
# two-character delimiter, and a tar-from-worktree shipped arm56.so -- and
# nothing noticed, because nothing ran them. A target nobody invokes is a
# target that rots; this one invokes all of them.
check: lint test check-no-binaries check-policy

# Aggregate policy gate. The individual targets stay callable so CI can
# attribute a failure to a specific policy.
check-policy: check-hardcoded-paths check-network-calls check-emoji check-legal-headers validate-config

.PHONY: check check-policy release release-dirty verify-release \
        check-no-binaries check-hardcoded-paths check-network-calls \
        check-emoji check-legal-headers validate-config
	@echo "All checks passed"

# Extract class manifests (Reflection) for a list of encrypted files
# Requires PHP 5.6 + the ionCube loader. Needs json_encode in the 5.6 build.
manifest:
	@test -n "$(FILES)" || (echo "usage: make manifest FILES=list.txt OUTPUT=dir" && exit 1)
	@test -n "$(OUTPUT)" || (echo "usage: make manifest FILES=list.txt OUTPUT=dir" && exit 1)
	python3 lib/class_manifest.py --files $(FILES) --source $(SOURCE) --output $(OUTPUT) \
		$(if $(CONFIG),--config $(CONFIG),)

# Extract arm56 symbol dumps for a list of encrypted files
symbols:
	@test -n "$(FILES)" || (echo "usage: make symbols FILES=list.txt OUTPUT=dir" && exit 1)
	@test -n "$(OUTPUT)" || (echo "usage: make symbols FILES=list.txt OUTPUT=dir" && exit 1)
	python3 lib/dump_batch.py --files $(FILES) --source $(SOURCE) --output $(OUTPUT) \
		$(if $(CONFIG),--config $(CONFIG),)

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

# Check no binary or build artifact is tracked in git.
#
# `make release` uses git archive, so the artifact is exactly the tracked file
# set. That makes this the gate that matters: .gitignore already keeps
# untracked build output out, but nothing stops `git add -f arm56/modules/
# arm56.so`, and a compiled extension in a release is both a legal problem
# (docs/LEGAL.md) and a CLAUDE.md "Never-Do".
check-no-binaries:
	@echo "Checking tracked files for binaries and build artifacts..."
	@# Every '$' here is doubled. In a Makefile recipe '$' introduces a
	@# variable reference, and "$$)" is not a regex anchor -- it silently
	@# becomes ")" and swallows the following "|", which is how an earlier
	@# version of this target passed while a tracked arm56.so was present.
	@bad=$$(git ls-files | grep -E '\.(so|a|o|lo|la|dylib|dll|exe|pyc)$$|(^|/)(\.libs|modules|autom4te\.cache)/|(^|/)configure$$|(^|/)config\.(h|log|status|nice)$$|(^|/)Makefile\.(global|objects|fragments)$$|(^|/)(aclocal\.m4|acinclude\.m4|libtool|ltmain\.sh|config\.(guess|sub)|run-tests\.php)$$' || true); \
	if [ -n "$$bad" ]; then \
		echo "FAIL: tracked build artifacts or binaries:" >&2; \
		echo "$$bad" >&2; \
		echo "Untrack them and rely on .gitignore (see CLAUDE.md, Never-Do)." >&2; \
		exit 1; \
	fi
	@echo "No tracked binaries or build artifacts"

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
	@# Not `head -10`: a module docstring routinely pushes SPDX past line 10,
	@# and six files here carry it between lines 17 and 33.
	@# Not `( ... && exit 1 )` either: that exits the subshell, the loop keeps
	@# going, and the trailing echo makes the recipe succeed. This target used
	@# to print FAIL for six files and still exit 0. No subshell, one shell.
	@missing=; \
	for f in lib/*.py lib/*.php bin/*; do \
		grep -q "SPDX-License-Identifier" "$$f" || missing="$$missing $$f"; \
	done; \
	if [ -n "$$missing" ]; then \
		echo "FAIL: missing SPDX-License-Identifier in:" >&2; \
		for f in $$missing; do echo "  $$f" >&2; done; \
		exit 1; \
	fi; \
	echo "All $$(ls lib/*.py lib/*.php bin/* | wc -l) file(s) have SPDX headers"

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

# Create release tarball plus a SHA-256 checksum.
#
# Built with `git archive`, not `tar -czf .`. The tar-from-worktree version
# shipped 112 files where git tracks 50, because it swept up every gitignored
# build artifact — including arm56/modules/arm56.so and arm56/.libs/arm56.so.
# A deny-list can never be complete; making "what ships" equal "what is
# committed" hands the job to .gitignore, which is where the binary rules
# already live (see CLAUDE.md, "Never-Do").
#
# The checksum is not decoration: tar and gzip embed mtimes and uid/gid, so
# rebuilding yields a different digest. A published checksum is meaningful only
# alongside the exact artifact it was taken from.
release: check
	@if [ -n "$$(git status --porcelain --untracked-files=no)" ]; then \
		echo "ERROR: tracked files are modified. A release must be built from" >&2; \
		echo "       a commit, or the tarball will not match the repository." >&2; \
		echo "       Commit first, or use 'make release-dirty' knowingly." >&2; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory release-dirty

# Same as release, without the clean-tree requirement. Produces an artifact that
# does NOT correspond to any commit; the checksum exists so that mismatch is
# detectable rather than silent.
release-dirty: check
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'"' -f2); \
	tmp=$$(mktemp -d); \
	git archive --format=tar.gz \
		--prefix="ioncube-strip-$${version}/" \
		-o "$$tmp/ioncube-strip-$${version}.tar.gz" HEAD && \
	mv "$$tmp/ioncube-strip-$${version}.tar.gz" . && rmdir "$$tmp"
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'"' -f2); \
	if command -v sha256sum >/dev/null 2>&1; then \
		sha256sum "ioncube-strip-$${version}.tar.gz" \
			> "ioncube-strip-$${version}.tar.gz.sha256"; \
	elif command -v shasum >/dev/null 2>&1; then \
		shasum -a 256 "ioncube-strip-$${version}.tar.gz" \
			> "ioncube-strip-$${version}.tar.gz.sha256"; \
	else \
		echo "ERROR: no sha256sum or shasum; refusing to ship an unchecksummed" >&2; \
		echo "       tarball. Install coreutils, or remove the checksum step" >&2; \
		echo "       deliberately and document why." >&2; \
		exit 1; \
	fi
	@echo "Created ioncube-strip-$$(grep '^VERSION=' bin/ioncube-strip | cut -d'"' -f2).tar.gz (+ .sha256)"

# Verify the release tarball: checksum first, then contents.
#
# Checksum before listing, because a listing proves only that tar can read the
# file. Verifying the digest is what proves the artifact is the one published.
verify-release:
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'"' -f2); \
	tarball="ioncube-strip-$${version}.tar.gz"; \
	[ -f "$$tarball" ] || { echo "FAIL: $$tarball not found; run 'make release'" >&2; exit 1; }
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'"' -f2); \
	tarball="ioncube-strip-$${version}.tar.gz"; \
	sum="$$tarball.sha256"; \
	if [ -f "$$sum" ]; then \
		if command -v sha256sum >/dev/null 2>&1; then \
			sha256sum -c "$$sum" || exit 1; \
		else \
			shasum -a 256 -c "$$sum" || exit 1; \
		fi; \
	else \
		echo "WARN: $$sum missing; contents listed but integrity NOT verified" >&2; \
	fi
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'"' -f2); \
	tar -tzf "ioncube-strip-$${version}.tar.gz" | head -20
	@version=$$(grep '^VERSION=' bin/ioncube-strip | cut -d'"' -f2); \
	if tar -tzf "ioncube-strip-$${version}.tar.gz" \
		| grep -E '(^|/)(aes|\.aes|\.git)/|\.so$$|__pycache__|\.pyc$$'; then \
		echo "FAIL: tarball contains excluded content" >&2; exit 1; \
	else \
		echo "tarball contains no excluded content"; \
	fi