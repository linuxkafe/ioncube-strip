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
| T009 | CI pipeline: lint, test, build | high | partial | M |
| T010 | Documentation: README, INSTALL, USAGE, CONFIGURATION, LEGAL | high | done | M |
| T011 | Reflection class manifests (`class_manifest.py` + `manifest`) | high | done | M |
| T012 | arm56 symbol dumps (`dump_batch.py` + `symbols`) | high | done | M |
| T013 | Shared stub/skip resolution loop (`stub_resolver.py`) | high | done | M |
| T014 | arm56 v4 extension vendored as first-party source | high | done | M |
| T015 | Honest quality gates: shellcheck, PHP 5.6 floor, Python 3.8 floor | high | done | M |
| T016 | arm56 generation probe + CLI guards against the wrong generation | high | done | S |
| T019 | Verbose/progress logging | medium | done | S |
| T022 | Release packaging: tarball + SHA-256, built from `git archive` | medium | done | S |

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

## Settled by measurement

The pool premise is now settled by evidence rather than inference. See
`docs/VALIDATION.md`.

- **T017 — settled against the pool path.** arm56's own output on WHMCS shows
  `content_faulted: true` and `num_ops: 0` for every encoded method, and
  `num_literals` as a count rather than content. There is no literal buffer to
  extract; this is not an implementation limitation. `dump`/`pool`/`run` stay
  in the tree, tested and labelled legacy, but no page advertises them as a
  capability.
- **Class shape is validated.** 90/90 class-bearing files, 1028 methods, two
  independent mechanisms agreeing exactly, under a second on four jobs.
- **Doc comments survive encryption** — 32.6% of symbols, 288 `@return` tags,
  24 distinct `@param` types. Undocumented in the requirements until now; it
  is real recovery value and belongs in the product description.
- **v1.0.0 is no longer blocked on T017.** The premise was decided; the
  product is `manifest` and `symbols`.

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T034 | Diagnose the 15 PHP 5.6 parse errors and 7 other fatals in the corpus | low | backlog | S |

## Sprint 2 — Polish & Distribution

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T018 | Dry-run mode for all subcommands | medium | done | S |
| T020 | Error handling improvements (continue on failure) | medium | done | S |
| T021 | Man page generation | low | pending | S |
| T023 | GitHub Actions: lint + unit + tool-free integration | medium | done | M |
| T030 | `make format` normalization: 21 files disagree with `ruff format` | low | pending | S |

## Sprint 3 — Extended Features (Post-1.0)

| ID | Title | Priority | Status | Effort |
|----|-------|----------|--------|--------|
| T024 | Reconstruction stub generator (reads manifests → emits PHP skeletons) | high | ready | M |
| T025 | Multiple ionCube version detection (heuristic) | low | backlog | L |
| T026 | Docker image with PHP 5.6 + arm56 v4 prebuilt | medium | backlog | M |
| T027 | Homebrew formula / AUR package | low | backlog | S |
| T028 | Web-based pool browser (optional) | low | backlog | XL |
| T029 | Return types in manifests (needs PHP 7 Reflection; unreachable at the 5.6 floor) | low | wontfix | S |

## Newly discovered (not yet scheduled)

Found while fixing the gates, after the tickets above were marked done. Listed
so they are not mistaken for oversights.

| ID | Title | Status |
|----|-------|--------|
| T031 | `--dry-run` requires a working toolchain. Defensible either way: it tells you the toolchain is broken, but it also means a dry run cannot preview on a machine without PHP 5.6. Needs a decision, not a fix. | open |
| T032 | T009 is only *partial*: the CI workflow lints and tests but never builds `arm56/`, which needs PHP 5.6 headers no runner has. | open |
| T033 | Python 3.8 has been EOL since Oct 2024 and is claimed in four places. Code honours the claim; whether the claim should stand is an owner decision. | open |

### T024 is now ready, and its fidelity is measured

A generator was written as a validation harness and is not in the repository.
Measured on WHMCS: **162 of 162 classes generate a skeleton that Reflection
reports as identical to the encrypted original** — parent, interfaces,
abstract, final, constants, own properties, own method signatures. 143/143
files parse and load under PHP 5.6.

Reclassified from `backlog`/`L` to `ready`/`M`: the hard part (mapping manifests
onto valid PHP 5.6 declarations) is solved and the remaining work is product
decisions, not research. Two need an owner:

1. **Empty bodies or throwing bodies?** Empty bodies produce a map. A body of
   `throw new \RuntimeException('not implemented')` produces something that
   loads and runs, which is a large practical difference.
2. **Licensing of emitted code.** Skeletons derived from WHMCS are derived work
   from proprietary source. `docs/LEGAL.md` covers the tool; it says nothing
   about output.

## Backlog (Unscheduled)

- Custom output formats for manifests (JSON, CSV, SQLite)
- Incremental scanning (skip already-processed files) — partly handled by the
  per-file manifests acting as a cache
- ARM64 support for the arm56 build
- Windows Subsystem for Linux (WSL) compatibility notes

## Milestones

1. **v0.1.0** — Core pipeline on a WHMCS test corpus (shipped). Its premise was
   later disproved; see "Settled by measurement"
2. **v0.2.0** — Class shape extraction: `manifest` + `symbols`, generation probe,
   honest gates, integration suite *(current)*
3. **v0.3.0** — Validated on WHMCS: 90/90 class files, 1028 methods, cross-check
   clean. Toolchain-present test tier running in CI where a toolchain exists
4. **v0.5.0** — CI on a PHP 5.6 runner, man pages, packaging
5. **v1.0.0** — Stable API, release artifacts, legal review. Not blocked: the
   product's scope was settled by measurement, and it is class shape
