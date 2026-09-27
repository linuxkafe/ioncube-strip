# ioncube-strip — Requirements

> **Status (v0.2.0).** FR-1 through FR-6 describe the legacy literal-pool
> pipeline. FR-1, FR-3, FR-4 and FR-6 are implemented but require the **legacy**
> arm56 extension, which is not in this repository; the extension here (v4)
> writes JSON and cannot feed them. Whether the pool *content* is recoverable
> at all is open — see `docs/ROADMAP.md` (T017).
>
> FR-7 and FR-8 are the currently supported path and work with the in-tree
> extension. Status per requirement: see the table at the end.

## Functional Requirements

### FR-0: arm56 Generation Identification
- Identify which arm56 extension is loaded before running any stage
- `lib/probe_arm56.py` calls `arm56_version()`; presence identifies v4
- Absence is reported as `unverified`, **never** inferred as legacy
- `dump` refuses to start against a v4 extension rather than reporting an
  empty success; `symbols` warns when the generation is `unverified`
- **Status: done**

### FR-1: Scan for Encrypted Files
- Recursively scan a source directory for PHP files containing ionCube 5.x markers
- Default markers: `_il_exec` (function call) and `// 00e5` (header comment)
- Configurable marker patterns via configuration file
- Output: newline-separated list of absolute file paths

### FR-2: Execute Under PHP 5.6 + arm56
- For each encrypted file, invoke PHP 5.6 CLI with arm56 extension loaded
- Execute the file (include) to trigger arm56 hooks on function entry
- arm56 writes RESERVED[3] hex dumps to `/tmp/arm56_output/` (fixed by extension)
- Configurable PHP binary path, INI path, arm56.so path
- Configurable output directory for collected dumps

### FR-3: Collect and Mirror Dumps
- After each file execution, copy arm56 output files to a mirrored directory structure
- Preserve source-relative paths under `dumps/`
- Handle multiple dump variants per function (arm56 produces `_0x*.txt` suffixes)
- Clean up `/tmp/arm56_output/` between files (or use unique temp dirs)

### FR-4: Extract Literal Pools
- Parse all dump files in the collected dumps directory
- Extract hex lines matching arm56 output format (`^  [0-9a-f]{4,8}: ((?:[0-9a-f]{2} )+)`)
- Convert hex to raw bytes
- Extract printable ASCII runs (default: `\x20-\x7e`, min length 3)
- Deduplicate runs per function (preserve first-appearance order)
- Configurable: min run length, character set, max run length
- Output: one text file per function (`pools/<func>.txt`) + index JSON (`pools/_index.json`)

### FR-5: CLI Interface
- Single entry point: `ioncube-strip`
- Subcommands: `scan`, `dump`, `pool`, `run` (full pool pipeline),
  `manifest`, `symbols` (class shape)
- Options: `--config`, `--source`, `--output`, `--files`, `--jobs`,
  `--rounds`, `--limit`, `--timeout`, `--dry-run`, `--verbose`
- Help text for each subcommand
- Version flag: `--version`
- `dump`/`pool`/`run` are documented as legacy and labelled as such in `--help`,
  `docs/USAGE.md` and `docs/CONFIGURATION.md`
- `--verbose` is accepted by every subcommand but currently has no effect
  (tracked as T019)
- **Status: done, except `--verbose`**

### FR-6: Configuration
- YAML configuration file (default: `config/ioncube-strip.yaml.example`)
- Sections: `toolchain`, `markers`, `output`, `extraction`, `parallelism`
- All CLI options overridable via config
- Schema validation on load, and it must not be a no-op under `python3 -O`

### FR-7: Reflection Class Manifests (`manifest`)
- Run one PHP 5.6 process per target under the ionCube Loader; arm56 not required
- Learn unresolved class/interface/trait names from the Loader's fatal, pre-declare
  them as empty stubs of the correct kind, and iterate to a fixpoint
- Declare a stub only for a symbol no successfully-loaded file has provided, so a
  real class is never shadowed
- Support a per-file skip when the file declares a symbol that was stubbed
  (`Cannot redeclare`), matched case-insensitively because the fatal lowercases
- Report per class: kind, abstract, final, parent, interfaces, constants, and
  **own** methods and properties only (inherited members excluded)
- Report per method: visibility, static, abstract, and per parameter name,
  optional, default, by-ref, and type hint — a hint naming an unloadable class
  yields null rather than aborting the file
- Output one JSON document per target plus `_manifest_report.json` carrying
  per-file state, learned stub symbols and skipped stubs
- Requires `json_encode`; if the 5.6 build lacks it, report it via
  `toolchain.php56_extra` rather than guessing
- **Status: done**

### FR-8: arm56 Symbol Dumps (`symbols`)
- Same stub-resolution loop as FR-7
- Call `arm56_dump()` and record the symbols the Loader registered
- Report per method: literal counts, and opcodes for plain PHP
- For encoded files report counts and signatures, not literal content
- Output one JSON document per target plus `_batch_report.json`
- Requires the v4 extension (`toolchain.arm56_so`)
- **Status: done**

### FR-9: Cross-Check
- Reflection (FR-7) and arm56 (FR-8) are independent mechanisms sharing only
  the file list; their agreement on the method count is therefore meaningful
- A disagreement is a defect signal, not noise
- The suite asserts agreement, never a constant: any corpus legitimately
  yields a different total
- **Status: done** (`tests/integration/test_extraction.py`, corpus tier)

## Non-Functional Requirements

### NFR-1: Offline Operation
- Zero network access at any stage
- No telemetry, no update checks, no license validation

### NFR-2: Portability
- No hardcoded paths (user home, project names, absolute paths)
- All paths configurable via CLI or config file
- Works on Linux (primary), macOS (secondary)

### NFR-3: Performance
- Parallel pool extraction using all CPU cores by default
- Streaming hex parsing (no full-file loading for large dumps)
- Configurable job count for dump execution (sequential by default due to shared `/tmp`)

### NFR-4: Reliability
- Exit codes: 0=success, 1=usage error, 2=runtime error, 3=config error
- Clear error messages with actionable suggestions
- Continue on individual file failures (log and proceed)

### NFR-5: Maintainability
- Python 3.8+ for all library code. The linter does **not** detect 3.9+ API use
  at that target; `tests/unit/test_python_floor.py` does, and
  `pyproject.toml` declares `target-version = "py38"` so ruff does not
  *recommend* 3.9+ APIs in the first place
- PHP 5.6 compatible for all shipped `.php` files. `php -l` on 8.x cannot prove
  this — it accepts 7.0+ syntax — so `tests/unit/test_php56_syntax.py` checks
  the floor directly
- No emojis, no network calls, no hardcoded paths — enforced by
  `make check-emoji`, `make check-network-calls`, `make check-hardcoded-paths`
- SPDX license identifier in all source files (`make check-legal-headers`)

### NFR-6: Legal Safety
- No ionCube decoder included
- The v4 arm56 extension source is included: `arm56/arm56.c` and
  `arm56/config.m4` only. Build artifacts (`.libs/`, `modules/`, `configure`,
  `*.lo`, ...) are never committed
- No encrypted test fixtures, ever. The corpus integration tier reads an
  operator-supplied tree via `IONCUBE_STRIP_CORPUS` instead
- Clear LEGAL.md with usage restrictions
- SPDX license identifier in all source files

## Technical Constraints

| Constraint | Detail |
|------------|--------|
| **Runtime** | PHP 5.6 CLI + ionCube Loader + arm56 (v4 in-tree, legacy external) |
| **Python** | 3.8+ (3.9+ APIs are a gate failure) |
| **PHP source** | 5.6 syntax floor; 7.0+ constructs are a gate failure |
| **Shell** | POSIX sh / bash for driver, shellcheck clean |
| **OS** | Linux (tested), macOS (untested) |
| **Disk** | ~100MB per 1000 encrypted files (dumps + pools), legacy path only |

## Acceptance Criteria

| ID | Criterion | Test Method | Status |
|----|-----------|-------------|--------|
| AC-1 | Scanner detects `_il_exec` and `// 00e5` markers | `test_find_encrypted.py`, `test_cli.py` | pass |
| AC-2 | `manifest` reports class shape under PHP 5.6 + Loader | `test_extraction.py`, toolchain tier | skipped without toolchain |
| AC-3 | `symbols` reports a document per target | `test_extraction.py`, toolchain tier | skipped without toolchain |
| AC-4 | Manifest and symbols agree on the method count | `test_extraction.py`, corpus tier | skipped without corpus |
| AC-5 | Config file overrides all defaults | unit tests | pass |
| AC-6 | No hardcoded paths in source | `make check-hardcoded-paths` in CI | pass |
| AC-7 | PHP 8.4 lint passes on all `.php` files | `php -l` in CI | pass |
| AC-8 | **Shipped `.php` files parse under PHP 5.6** | `test_php56_syntax.py` | pass |
| AC-9 | **`lib/` uses no 3.9+ API** | `test_python_floor.py` | pass |
| AC-10 | Python ruff passes on `lib/ tests/ scripts/` | `ruff check` in CI | pass |
| AC-11 | Shellcheck passes, and a finding **fails** the gate | `shellcheck` in CI; verified by injecting a finding | pass |
| AC-12 | The wrong arm56 generation is refused, not silently empty | `test_probe_arm56.py` + CLI guard | pass |
| AC-13 | `dump`/`pool` produce pools from legacy hex dumps | `test_extract_pools.py`, `test_cli.py` on synthetic input | pass (legacy generation only) |
| AC-14 | A fully-skipped integration run is reported as such | CI counts and prints skips; fails if zero | pass |

AC-2, AC-3 and AC-4 cannot run in CI: they need PHP 5.6, the ionCube Loader and
an encrypted corpus, none of which may be committed. A green CI run is not
evidence for them.