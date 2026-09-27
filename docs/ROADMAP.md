# ioncube-strip — Roadmap

Statuses are reconciled against the tree, not against intent. A ticket is
`done` only when the code exists **and** a gate covers it.

## Current Sprint: Sprint 1 — Core Toolkit

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T001 | Project scaffolding + AES structure | high | done | S |
| T002 | Refactor `find_encrypted.py` — configurable markers, no hardcoded paths | high | done | M |
| T003 | Refactor `dump_one.php` — minimal, configurable | high | done | S |
| T004 | Refactor `extract_pools.py` — configurable I/O, patterns, parallelism | high | done | M |
| T005 | Create `ioncube-strip` CLI driver (bash) with subcommands | high | done | M |
| T006 | Configuration file schema (YAML) + validation | high | done | S |
| T007 | Unit tests for pool extraction (synthetic dumps) | high | done | M |
| T008 | Integration test harness (two tiers: tool-free + toolchain/corpus) | medium | done | L |
| T009 | CI pipeline: lint, test, build | high | pending | M |
| T010 | Documentation: README, INSTALL, USAGE, CONFIGURATION, LEGAL | high | done | M |
| T011 | Reflection class manifests (`class_manifest.py` + `manifest`) | high | done | M |
| T012 | arm56 symbol dumps (`dump_batch.py` + `symbols`) | high | done | M |
| T013 | Shared stub/skip resolution loop (`stub_resolver.py`) | high | done | M |
| T014 | arm56 v4 extension vendored as first-party source | high | done | M |
| T015 | Honest quality gates: shellcheck, PHP 5.6 floor, Python 3.8 floor | high | done | M |
| T016 | arm56 generation probe + CLI guards against the wrong generation | high | done | S |

## Open — the pool premise

The project's original purpose was literal pool extraction. That premise is now
contested by our own evidence, not by outside opinion:

- `arm56/arm56.c` is the v4 spike. It serialises op_arrays to JSON and has no
  hex writer (`grep -c hex arm56/arm56.c` → 0), so it cannot feed
  `collect_dumps.py` / `extract_pools.py` at all.
- `docs/CONFIGURATION.md` records that the Loader frees the pool once a body
  has run, `zend_execute_ex` is not re-entered for encoded code, and
  `op_array->reserved[3]` is NULL for encoded code.

If the second finding is right, `dump` and `pool` have no output to produce
regardless of which arm56 is installed, and `extract_pools.py` is dead by
design. The code is kept and tested, and the CLI refuses to run `dump` against
a v4 extension rather than reporting a silent empty success, but no claim is
made that it works.

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T017 | Settle the pool premise: run `dump`/`pool` against a legacy build on a real corpus, or retire them | high | blocked | M |

T017 is blocked on external inputs (a legacy arm56 build and a real corpus),
neither of which belongs in this repository.

## Sprint 2 — Polish & Distribution

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T018 | Dry-run mode for all subcommands | medium | done | S |
| T019 | Verbose/progress logging — `--verbose` is parsed by every subcommand and currently does nothing | medium | stub | S |
| T020 | Error handling improvements (continue on failure) | medium | done | S |
| T021 | Man page generation | low | pending | S |
| T022 | Release packaging (tarball, checksums) | medium | pending | S |
| T023 | GitHub Actions: lint + unit + tool-free integration on a matrix | medium | pending | M |

## Sprint 3 — Extended Features (Post-1.0)

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T024 | Reconstruction stub generator (reads manifests → emits PHP skeletons) | medium | backlog | L |
| T025 | Multiple ionCube version detection (heuristic) | low | backlog | L |
| T026 | Docker image with PHP 5.6 + arm56 v4 prebuilt | medium | backlog | M |
| T027 | Homebrew formula / AUR package | low | backlog | S |
| T028 | Web-based pool browser (optional) | low | backlog | XL |
| T029 | Return types in manifests (needs PHP 7 Reflection; unreachable at the 5.6 floor) | low | wontfix | S |

## Backlog (Unscheduled)

- Custom output formats for manifests (JSON, CSV, SQLite)
- Incremental scanning (skip already-processed files) — partly handled by the
  per-file manifests acting as a cache
- ARM64 support for the arm56 build
- Windows Subsystem for Linux (WSL) compatibility notes

## Milestones

1. **v0.1.0** — Core pipeline on a WHMCS test corpus (shipped)
2. **v0.2.0** — Class shape extraction: `manifest` + `symbols`, generation probe,
   honest gates, integration suite *(current)*
3. **v0.5.0** — CI passing, packaging, man pages
4. **v1.0.0** — Stable API, release artifacts, legal review. **Blocked on T017**:
   the product's headline capability must be decided before a 1.0 claim.
