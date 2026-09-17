# ioncube-strip — Requirements

## Functional Requirements

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
- Subcommands: `scan`, `dump`, `pool`, `run` (full pipeline)
- Options: `--config`, `--source`, `--output`, `--dry-run`, `--verbose`, `--jobs`
- Help text for each subcommand
- Version flag: `--version`

### FR-6: Configuration
- YAML configuration file (default: `ioncube-strip.yaml` in CWD or `~/.config/ioncube-strip/`)
- Sections: `toolchain`, `markers`, `output`, `extraction`, `parallelism`
- All CLI options overridable via config
- Schema validation on load

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
- Python 3.8+ for pool extraction (standard library only where possible)
- PHP 5.6 compatible for dump scripts (no modern syntax)
- Shell POSIX-compliant for driver script
- Type hints in Python; docstrings in all files

### NFR-6: Legal Safety
- No ionCube decoder included
- No arm56 source included (separate build)
- Clear LEGAL.md with usage restrictions
- SPDX license identifier in all source files

## Technical Constraints

| Constraint | Detail |
|------------|--------|
| **Runtime** | PHP 5.6 CLI + arm56.so (user-provided) |
| **Python** | 3.8+ (for pool extraction) |
| **Shell** | POSIX sh / bash for driver |
| **OS** | Linux (tested), macOS (untested) |
| **Disk** | ~100MB per 1000 encrypted files (dumps + pools) |

## Acceptance Criteria

| ID | Criterion | Test Method |
|----|-----------|-------------|
| AC-1 | Scanner detects `_il_exec` and `// 00e5` markers | Unit test with fixture files |
| AC-2 | Dump executes file under PHP 5.6 + arm56 | Integration test (requires toolchain) |
| AC-3 | Pool extractor produces deduped ASCII runs | Unit test with synthetic arm56 output |
| AC-4 | CLI `run` executes full pipeline | Integration test with test corpus |
| AC-5 | Config file overrides all defaults | Unit test: load config, verify values |
| AC-6 | No hardcoded paths in source | Grep check in CI |
| AC-7 | PHP 8.4 lint passes on all .php files | `php -l` in CI |
| AC-8 | Python ruff passes | `ruff check` in CI |
| AC-9 | Shellcheck passes | `shellcheck` in CI |