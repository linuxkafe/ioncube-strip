# ioncube-strip — Solution Proposal (Phase 2)

> **Superseded in part (2026-09-27, v0.2.0).** Historical record of the
> original proposal. Two of its claims no longer hold:
>
> 1. **"arm56 build not included — documented as prerequisite"** is no longer
>    true. `arm56/arm56.c` (v4) is now first-party source in this repository.
>    It serialises op_arrays to JSON and has no hex writer, so it cannot feed
>    the `dump`→`pool` half of the architecture diagram below.
> 2. **"Core algorithm: arm56 runtime dumping → hex parsing → ASCII run
>    extraction"** is contested. `docs/CONFIGURATION.md` records that the
>    Loader frees the literal pool and `op_array->reserved[3]` is NULL for
>    encoded code, which would mean the hex-parsing stage has nothing to parse
>    even with a legacy build. Tracked as `docs/ROADMAP.md` T017.
>
> What shipped instead: `manifest` and `symbols`, recovering class shape via
> two independent mechanisms. See `docs/REQUIREMENTS.md` (FR-7, FR-8) and
> `aes/kanban.md`.

## Chosen Approach

Create a **project-agnostic, configurable toolkit** for ionCube 5.x runtime dumping and literal pool extraction. The tool consists of:

1. **`find_encrypted.py`** — Recursive scanner for ionCube markers (configurable patterns)
2. **`dump_one.py`** — Single-file executor under PHP 5.6 + arm56 (minimal, no logic)
3. **`extract_pools.py`** — Parallel pool extractor (configurable input/output, regex patterns)
4. **`ioncube-strip`** — Main CLI driver (bash or Python) orchestrating the pipeline
5. **Configuration file** — YAML/JSON for toolchain paths, markers, output structure

## What Will Change (vs. WHMCS version)

| Component | WHMCS Version | New Version |
|-----------|---------------|-------------|
| Paths | Hardcoded `/home/seyon/`, WHMCS-specific | Configurable via CLI args + config file |
| Markers | `_il_exec` or `// 00e5` only | Extensible pattern list (default: same) |
| Pool prefix | WHMCS-specific filename pattern | Derived from source root + configurable delimiter |
| Output layout | Fixed `dumps/` + `pools/` | Configurable, with sensible defaults |
| Parallelism | `os.cpu_count()` | Configurable (default: all cores) |
| Encoding | ASCII only | Configurable (ASCII default, UTF-8 option) |

## What Will NOT Change

- Core algorithm: arm56 runtime dumping → hex parsing → ASCII run extraction → dedup
- Offline-only operation (no network)
- PHP 5.6 + arm56 as required runtime
- Output: per-function literal pools + index JSON

## Architecture

```
ioncube-strip (CLI entry point)
    │
    ├── config.yaml (toolchain paths, markers, output)
    │
    ├── find_encrypted.py → [list of encrypted files]
    │
    ├── dump_one.php (executed per file via PHP 5.6 + arm56)
    │       └── writes to /tmp/arm56_output/ (arm56 behavior)
    │
    ├── collect_dumps.py → mirrors arm56 output to configured dumps/
    │
    └── extract_pools.py → reads dumps/, writes pools/ + _index.json
```

## Verification Criteria (Definition of Done)

| Criterion | How Verified |
|-----------|--------------|
| **Scan finds encrypted files** | Unit test with fixture files containing `_il_exec` and `// 00e5` |
| **Dump executes without error** | Integration test: run on sample encrypted file, check `/tmp/arm56_output/` |
| **Pools extracted correctly** | Unit test: feed synthetic arm56 output, verify deduped ASCII runs |
| **CLI works end-to-end** | Integration test: `ioncube-strip scan dump pool <testdir> <outdir>` |
| **Configurable paths** | Test: override all paths via config file, verify respected |
| **No hardcoded WHMCS paths** | Grep: no `/home/seyon/`, no `whmcs` in source (except tests/docs) |
| **PHP 8.4 lint clean** | `php -l` on all `.php` files in repo |
| **Python lint clean** | `ruff check` on all `.py` files |
| **Shellcheck clean** | `shellcheck` on all `.sh` files |
| **Docs complete** | README, INSTALL, USAGE, LEGAL, CONFIGURATION |

## Acceptance Tests

1. **Happy path**: Point at a directory with 1 known ionCube 5.x file → produces pool file with expected strings
2. **Config override**: Change output directory via config → pools written to new location
3. **Marker extensibility**: Add custom marker pattern → scanner detects it
4. **Dry-run mode**: `--dry-run` shows what would be done without executing
5. **Error handling**: Missing PHP 5.6 → clear error message; missing arm56.so → clear error

## Remaining Risks (Accepted)

- **arm56 build not included** — Documented as prerequisite; provide build instructions
- **No test corpus in repo** — Legal risk; use synthetic dumps for unit tests only
- **ionCube version detection** — Not implemented; assume 5.x based on markers