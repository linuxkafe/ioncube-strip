# ioncube-strip — Roadmap

## Current Sprint: Sprint 1 — Core Toolkit

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T001 | Project scaffolding + AES structure | high | done | S |
| T002 | Refactor `find_encrypted.py` — configurable markers, no hardcoded paths | high | in-progress | M |
| T003 | Refactor `dump_one.php` — minimal, configurable | high | pending | S |
| T004 | Refactor `extract_pools.py` — configurable I/O, patterns, parallelism | high | pending | M |
| T005 | Create `ioncube-strip` CLI driver (bash) with subcommands | high | pending | M |
| T006 | Configuration file schema (YAML) + validation | high | pending | S |
| T007 | Unit tests for pool extraction (synthetic dumps) | high | pending | M |
| T008 | Integration test harness (requires PHP 5.6 + arm56) | medium | pending | L |
| T009 | CI pipeline: lint, test, build | high | pending | M |
| T010 | Documentation: README, INSTALL, USAGE, CONFIGURATION, LEGAL | high | pending | M |

## Sprint 2 — Polish & Distribution

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T011 | Dry-run mode for all subcommands | medium | pending | S |
| T012 | Verbose/progress logging | medium | pending | S |
| T013 | Error handling improvements (continue on failure) | medium | pending | S |
| T014 | Man page generation | low | pending | S |
| T015 | Release packaging (tarball, checksums) | medium | pending | S |
| T016 | GitHub Actions: test matrix (Ubuntu, macOS) | medium | pending | M |

## Sprint 3 — Extended Features (Post-1.0)

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T017 | Reconstruction stub generator (reads pools → emits PHP skeletons) | medium | backlog | L |
| T018 | Multiple ionCube version detection (heuristic) | low | backlog | L |
| T019 | Docker image with PHP 5.6 + arm56 prebuilt | medium | backlog | M |
| T020 | Homebrew formula / AUR package | low | backlog | S |
| T021 | Web-based pool browser (optional) | low | backlog | XL |

## Backlog (Unscheduled)

- Support for custom output formats (JSON, CSV, SQLite)
- Incremental scanning (skip already-processed files)
- Parallel dump execution (requires isolated temp dirs per job)
- ARM64 support for arm56 build
- Windows Subsystem for Linux (WSL) compatibility notes

## Milestones

1. **v0.1.0** — Core pipeline works end-to-end on WHMCS test corpus (Sprint 1)
2. **v0.5.0** — Configurable, tested, documented, CI passing (Sprint 2)
3. **v1.0.0** — Stable API, man pages, release artifacts, legal review (Sprint 2 end)
4. **v1.1.0** — Stub generator, Docker image (Sprint 3)