# ioncube-strip — Operational Contract

## Intent

Build a project-agnostic, offline toolkit for recovering the *shape* of ionCube
5.x encrypted PHP files: which classes exist, what they extend, and what
methods they declare. Target users: developers recovering abandoned software,
license recovery, digital preservation.

Two capabilities exist and they are not equally supported. Read
`docs/CONFIGURATION.md` ("Two arm56 generations") before assuming either works.

| Capability | Stage | Status |
|---|---|---|
| Class shape, method signatures, literal counts | `manifest`, `symbols` | Works with the in-tree v4 extension |
| Literal pool strings | `dump`, `pool` | Needs the legacy arm56 build, which is **not** in this repo. May have no output to produce at all — see below. |

The literal-pool premise is contested by our own findings: `docs/CONFIGURATION.md`
records that the Loader frees the pool once a body has run and
`op_array->reserved[3]` is NULL for encoded code. Treat `extract_pools.py` as
unproven, not as the product's core.

## Non-Goals

- IonCube 6.x/10.x/12.x support
- Automated decompilation or source reconstruction
- Network access of any kind
- GUI or web interface
- Building PHP 5.6 itself (external dependency)

## Critical Files

- `bin/ioncube-strip` — CLI entry point (bash): `scan`, `dump`, `pool`, `manifest`, `symbols`, `run`
- `arm56/arm56.c` — the v4 extension, first-party source (JSON op_array dumps)
- `lib/probe_arm56.py` — identifies which arm56 generation is loaded
- `lib/stub_resolver.py` — shared stub/skip resolution loop (Python 3.8+)
- `lib/class_manifest.py` — Reflection manifests (Python 3.8+)
- `lib/dump_batch.py` — arm56 symbol dumps (Python 3.8+)
- `lib/find_encrypted.py` — Scanner (Python 3.8+)
- `lib/dump_one.php` — Single-file executor (**PHP 5.6**)
- `lib/collect_dumps.py` — Legacy hex-dump collector (Python 3.8+)
- `lib/extract_pools.py` — Legacy pool extractor (Python 3.8+)
- `config/ioncube-strip.yaml.example` — Configuration template
- `tests/unit/` — no external toolchain required
- `tests/integration/` — two tiers: tool-free (always runs) and toolchain/corpus (skips)

## Essential Commands

```bash
# Install dependencies (Python)
pip install -r requirements.txt  # pyyaml, ruff (dev)

# Full gate: ruff (lib/ tests/ scripts/) + shellcheck + php -l + unit tests
make check

# Test (unit only - no PHP 5.6 toolchain)
python3 -m pytest tests/unit -v

# Integration tests
#   Tool-free tier always runs. The toolchain/corpus tier skips unless set:
export IONCUBE_STRIP_PHP56=/path/to/php5.6
export IONCUBE_STRIP_INI=/path/to/php56.ini
export IONCUBE_STRIP_ARM56=/path/to/arm56.so
export IONCUBE_STRIP_CORPUS=/path/to/encrypted/tree   # optional
python3 -m pytest tests/integration -v

# Which arm56 is loaded?
python3 lib/probe_arm56.py --config config/ioncube-strip.yaml.example

# Run on a source tree
./bin/ioncube-strip run --source /path/to/encrypted --output /path/to/workdir

# Subcommands
./bin/ioncube-strip scan     --source /path/to/encrypted
./bin/ioncube-strip dump     --source /path/to/encrypted --output /path/to/workdir
./bin/ioncube-strip pool     --dumps /path/to/workdir/dumps --output /path/to/workdir
./bin/ioncube-strip manifest --files files.list --output /path/to/manifests
./bin/ioncube-strip symbols  --files files.list --output /path/to/symbols
```

## Never-Do

- Never hardcode paths (`/home/`, `/tmp/arm56_output/`, project names)
- Never add network calls (no HTTP, no DNS, no update checks)
- Never commit test fixtures with real encrypted code (legal risk)
- Never commit `arm56.so`, any PHP 5.6 binary, or any arm56 build artifact
  (`arm56/.libs/`, `arm56/modules/`, `arm56/configure`, `arm56/*.lo`, ...)
- Never use emojis in source code or commit messages
- Never assume PHP 5.6 is in PATH — always configurable
- Never use PHP 7+ syntax in a shipped `.php` file, and never a 3.9+ API in
  `lib/` — the floors are 5.6 and 3.8, and the linters cannot catch either

## Evidence Required

- All Python files: `ruff check lib/ tests/ scripts/` clean
- All PHP files: `php -l` clean under PHP 8.4 **and** `pytest tests/unit/test_php56_syntax.py`
  (PHP 8.4 accepts 7.0+ syntax; it cannot prove the 5.6 floor)
- All shell scripts: `shellcheck` clean, and `make lint` must actually fail on
  a finding — never re-add a `cmd || echo "not installed"` that swallows it
- Python floor: `pytest tests/unit/test_python_floor.py`
- Unit tests pass without external toolchain
- Integration tests document which tier needs what; a fully-skipped run is not
  a pass and must not be reported as one
- Config file schema validated on load
- LEGAL.md reviewed before each release
