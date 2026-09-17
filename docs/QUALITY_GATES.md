# ioncube-strip — Quality Gates

## Domain-Specific Gates

This project is a **CLI toolkit** (Python + PHP + Bash) for offline binary analysis.
No web, no database, no network.

## Gate Definitions

### G1: Python Code Quality
```bash
ruff check lib/ tests/
ruff format --check lib/ tests/
```
- **Blocker**: Any error (E, F, W)
- **Warning**: Unused imports (F401) in test fixtures only

### G2: PHP Code Quality
```bash
php -l lib/dump_one.php
php -l lib/collect_dumps.php  # if exists
```
- **Blocker**: Any parse error
- **Target**: PHP 8.4 compatibility (lint under 8.4)

### G3: Shell Script Quality
```bash
shellcheck bin/ioncube-strip
bash -n bin/ioncube-strip
```
- **Blocker**: Any error (SC1xxx, SC2xxx)
- **Warning**: Style suggestions (SC2xxx)

### G4: Unit Tests
```bash
python -m pytest tests/unit -v --tb=short
```
- **Blocker**: Any test failure
- **Coverage**: Not enforced (toolkit, not library)

### G5: Configuration Validation
```bash
python -c "
import yaml, sys
schema = {
    'toolchain': dict,
    'markers': list,
    'output': dict,
    'extraction': dict,
    'parallelism': dict
}
data = yaml.safe_load(sys.stdin)
for k, t in schema.items():
    assert k in data, f'Missing section: {k}'
    assert isinstance(data[k], t), f'Wrong type for {k}'
" < config/ioncube-strip.yaml.example
```
- **Blocker**: Schema validation failure

### G6: Hardcoded Path Check
```bash
# Must return empty
grep -r "/home/" lib/ bin/ config/ | grep -v ".example" | grep -v "test" || true
grep -r "whmcs" lib/ bin/ config/ | grep -v ".example" | grep -v "test" || true
grep -r "/tmp/arm56" lib/ bin/ config/ | grep -v ".example" | grep -v "test" || true
```
- **Blocker**: Any match outside test fixtures

### G7: Network Call Check
```bash
# Must return empty
grep -r -E "(http|https)://" lib/ bin/ config/ || true
grep -r -E "(curl|wget|requests|urllib|httpx|aiohttp)" lib/ bin/ config/ || true
grep -r -E "socket\." lib/ bin/ config/ || true
```
- **Blocker**: Any match

### G8: Emoji Check
```bash
# Must return empty
grep -r -P "[\xF0-\xF4][\x80-\xBF]{3}" lib/ bin/ tests/ config/ || true
```
- **Blocker**: Any match

### G9: Legal Header Check
```bash
# All source files must have SPDX header
for f in lib/*.py lib/*.php bin/*; do
    head -10 "$f" | grep -q "SPDX-License-Identifier" || exit 1
done
```
- **Blocker**: Missing header

## CI Pipeline (GitHub Actions)

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install deps
        run: pip install -r requirements.txt
      - name: Python lint
        run: ruff check lib/ tests/
      - name: Python format check
        run: ruff format --check lib/ tests/
      - name: Unit tests
        run: python -m pytest tests/unit -v
      - name: Config validation
        run: python scripts/validate_config.py
      - name: Hardcoded path check
        run: ./scripts/check_hardcoded_paths.sh
      - name: Network call check
        run: ./scripts/check_network_calls.sh
      - name: Emoji check
        run: ./scripts/check_emoji.sh
      - name: Legal header check
        run: ./scripts/check_legal_headers.sh

  php-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup PHP 8.4
        uses: shivammathur/setup-php@v2
        with: { php-version: '8.4' }
      - name: PHP lint
        run: php -l lib/dump_one.php

  shell-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install shellcheck
        run: sudo apt-get install -y shellcheck
      - name: Shell lint
        run: shellcheck bin/ioncube-strip
      - name: Shell syntax
        run: bash -n bin/ioncube-strip
```

## Pre-Release Gate

All above gates must pass on `main` branch before tagging a release.

## Integration Test Gate (Manual)

```bash
# Requires: PHP 5.6 + arm56 built and configured
export PHP56=/path/to/php5.6
export PHP56_INI=/path/to/php56.ini
export ARM56_SO=/path/to/arm56.so
python -m pytest tests/integration -v
```
- **Not in CI** — Requires specialized toolchain
- **Documented** in `tests/integration/README.md`
- **Run manually** before major releases