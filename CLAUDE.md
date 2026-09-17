# ioncube-strip — Operational Contract

## Intent

Build a project-agnostic, offline toolkit for extracting literal pools from ionCube 5.x encrypted PHP files. Target users: developers recovering abandoned software, license recovery, digital preservation.

## Non-Goals

- IonCube 6.x/10.x/12.x support
- Automated decompilation or source reconstruction
- Network access of any kind
- GUI or web interface
- arm56 extension build (external dependency)

## Critical Files

- `bin/ioncube-strip` — Main CLI entry point (bash)
- `lib/find_encrypted.py` — Scanner (Python 3.8+)
- `lib/dump_one.php` — Single-file executor (PHP 5.6)
- `lib/extract_pools.py` — Pool extractor (Python 3.8+)
- `lib/collect_dumps.py` — Dump collector (Python 3.8+)
- `config/ioncube-strip.yaml.example` — Configuration template
- `tests/` — Unit and integration tests

## Essential Commands

```bash
# Install dependencies (Python)
pip install -r requirements.txt  # pyyaml, ruff (dev)

# Lint
ruff check lib/ tests/
shellcheck bin/ioncube-strip
php -l lib/dump_one.php

# Test (unit only - no PHP 5.6 toolchain)
python -m pytest tests/unit -v

# Integration test (requires PHP 5.6 + arm56)
export PHP56=/path/to/php5.6
export ARM56_SO=/path/to/arm56.so
export PHP56_INI=/path/to/php56.ini
python -m pytest tests/integration -v

# Run on a source tree
./bin/ioncube-strip run --source /path/to/encrypted --output /path/to/workdir

# Subcommands
./bin/ioncube-strip scan --source /path/to/encrypted
./bin/ioncube-strip dump --source /path/to/encrypted --output /path/to/workdir
./bin/ioncube-strip pool --dumps /path/to/workdir/dumps --output /path/to/workdir/pools
```

## Never-Do

- Never hardcode paths (`/home/`, `/tmp/arm56_output/`, project names)
- Never add network calls (no HTTP, no DNS, no update checks)
- Never commit test fixtures with real encrypted code (legal risk)
- Never include arm56.so or PHP 5.6 binaries in repo
- Never use emojis in source code or commit messages
- Never assume PHP 5.6 is in PATH — always configurable

## Evidence Required

- All Python files: `ruff check` clean
- All PHP files: `php -l` clean under PHP 8.4
- All shell scripts: `shellcheck` clean
- Unit tests pass without external toolchain
- Integration tests documented as requiring PHP 5.6 + arm56
- Config file schema validated on load
- LEGAL.md reviewed before each release