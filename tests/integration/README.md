# Integration tests

Two tiers, and **a run where the second tier skips is not a pass**. It means the
first tier passed and the extraction pipeline was never exercised on real input.

## Tier 1 — tool-free (always runs)

`test_cli.py`. Drives the real `bin/ioncube-strip` and the real
`lib/find_encrypted.py` and `lib/extract_pools.py` over synthetic inputs
generated per test. Needs no PHP 5.6, no arm56, no corpus.

This is the only tier that can regress in an ordinary pull request, and the
only one that runs in CI. It covers: scanning, pool extraction and
deduplication, per-subcommand argument validation, `--dry-run` for every
subcommand, and `--help` coverage.

Fixtures are built at run time rather than committed, for two reasons: a
committed dump fixture is a second thing to keep in sync with the parser's
format, and `tests/integration/conftest.py` documents the two couplings that
matter (the `.fn.` filename marker, and the trailing space the hex regex
requires on the last byte pair of a line).

## Tier 2 — toolchain and corpus (skips unless configured)

`test_extraction.py`. Needs PHP 5.6, the ionCube Loader and arm56, and for the
corpus tests a tree of encrypted files. Skips are reported with `-rs`.

```bash
export IONCUBE_STRIP_PHP56=/usr/local/bin/php5.6
export IONCUBE_STRIP_INI=/etc/php56/php.ini
export IONCUBE_STRIP_ARM56=/usr/local/lib/arm56.so

# Optional: an operator-supplied tree of encrypted .php files
export IONCUBE_STRIP_CORPUS=/path/to/encrypted/tree

python3 -m pytest tests/integration -v -rs
```

| Variable | Needed by | If unset |
|---|---|---|
| `IONCUBE_STRIP_PHP56` | toolchain tests | skip |
| `IONCUBE_STRIP_INI` | toolchain tests | skip |
| `IONCUBE_STRIP_ARM56` | arm56 tests | skip |
| `IONCUBE_STRIP_CORPUS` | corpus tests, incl. the cross-check | skip |

The `IONCUBE_STRIP_` prefix is deliberate: it keeps these out of the
`PHP56` / `ARM56_SO` namespace that `lib/dump_batch.py` reads, so a test run
cannot silently pick up a developer's shell configuration.

## Why there is no committed corpus

A fixture containing ionCube-encoded third-party PHP is a legal liability, and
`docs/LEGAL.md` and `CLAUDE.md` both forbid it. The corpus is therefore always
supplied from outside the repository. This is a real coverage limitation, not an
oversight: nothing in CI can exercise the extraction path.

The CI workflow counts skipped tests, prints the count, and **fails if the
count is zero** — a silently empty tier is worse than a skipping one.

## The cross-check

`test_manifest_and_symbols_agree_on_the_method_count` compares two mechanisms
that share nothing but the file list:

- `manifest` — Reflection, via the Loader's own inheritance resolution
- `symbols` — `arm56_dump()`, i.e. the symbols the Loader registered

Where they disagree on the method count, one of them is wrong. That is a defect
signal, not noise, and it is why the test asserts *agreement* rather than any
constant: `docs/CONFIGURATION.md` quotes 1028 methods across 104 files for one
WHMCS corpus, but that is an observation about that corpus, not an invariant of
the tools.
