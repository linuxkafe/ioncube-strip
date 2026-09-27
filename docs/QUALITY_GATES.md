# ioncube-strip — Quality Gates

## The one rule this document exists to enforce

**A gate that cannot fail is not a gate.** Every definition below is a command
you can run and a non-zero exit you can observe. If a check needs `|| true`,
`|| echo`, or any construct that swallows a non-zero status, it is a report,
not a gate — label it as one.

The historical defect in this repository was
`which shellcheck >/dev/null && shellcheck bin/ioncube-strip || echo "shellcheck
not installed, skipping"`. The `||` fired on *any* non-zero exit from
`shellcheck`, not only on "command not found", so two genuine findings were
suppressed while the gate reported success. The availability check and the run
are now separate steps.

## Blockers

| ID | Check | Command | Enforced by |
|----|-------|---------|-------------|
| G1 | Python lint | `ruff check lib/ tests/ scripts/` | `make lint`, CI |
| G2 | PHP parses | `php -l lib/dump_one.php` | `make lint`, CI |
| G3 | Shell lint | `shellcheck bin/ioncube-strip` | `make lint`, CI |
| G4 | Unit tests | `python3 -m pytest tests/unit` | `make check`, CI |
| G5 | Tool-free integration tests | `python3 -m pytest tests/integration` | `make test-integration`, CI |
| G6 | No hardcoded paths | `make check-hardcoded-paths` | via `make check`, CI |
| G7 | No network calls | `make check-network-calls` | via `make check`, CI |
| G8 | No emojis | `make check-emoji` | via `make check`, CI |
| G9 | SPDX headers | `make check-legal-headers` | via `make check`, CI |
| G10 | Config schema | `make validate-config` | via `make check`, CI |
| G11 | **PHP 5.6 syntax floor** | `pytest tests/unit/test_php56_syntax.py` | via G4, CI |
| G12 | **Python 3.8 API floor** | `pytest tests/unit/test_python_floor.py` | via G4, CI |
| G13 | **arm56 generation classification** | `pytest tests/unit/test_probe_arm56.py` | via G4, CI |
| G14 | No tracked binary or build artifact | `make check-no-binaries` | via `make check`, CI |
| G15 | CLI flag forwarding and `--verbose` | `pytest tests/integration/test_cli.py` | via G5, CI |
| G16 | Release artifact integrity | `make release && make verify-release` | manual, pre-release only |

`make check` is the single gate: `lint`, `test`, `check-no-binaries` and
`check-policy` (which aggregates G6-G10). G6-G10 also run as individual targets
so CI can attribute a failure to a specific policy.

### G14 exists because `release` ships the tracked file set

`make release` uses `git archive`, so the artifact is exactly what is committed.
That makes the tracked set the thing that must be free of binaries:
`.gitignore` keeps untracked build output out, but nothing stopped
`git add -f arm56/modules/arm56.so`, and a compiled extension in a release is
both a legal problem (`docs/LEGAL.md`) and a `CLAUDE.md` "Never-Do".

The previous release target used `tar -czf .` over the working tree, which
shipped 112 files where git tracked 50 — including `arm56/modules/arm56.so` and
`arm56/.libs/arm56.so`. A deny-list can never be complete; `git archive` hands
the job to `.gitignore`.

### G16: verify the checksum, not just the listing

`make verify-release` checks the SHA-256 before listing contents, and warns
loudly if the `.sha256` file is missing rather than passing silently. A listing
proves only that `tar` can read the file; the digest is what proves the artifact
is the one published. Verified by appending a byte to the tarball: the check
reports `FAILED`.

Note that `tar` and `gzip` embed mtimes and uid/gid, so rebuilding yields a
different digest. A published checksum is meaningful only next to the exact
artifact it was taken from — which is why `release` refuses to build from a
modified working tree and `release-dirty` exists as a knowingly-different path.

## Warnings

| ID | Check | Note |
|----|-------|------|
| G17 | `ruff format --check lib/ tests/ scripts/` | **Not clean: 21 of 22 files disagree.** Deliberately not applied — see T030. `make format` currently rewrites 21 files, so run it as its own reviewed commit, never mixed into a change |

## Why the floors are tests and not linters

G11 and G12 are the two gates that exist because the obvious tool is
structurally unable to do the job.

- **`php -l` on PHP 8.4 cannot prove a PHP 5.6 floor.** 8.4 accepts 7.0+
  syntax, so `$argv[1] ?? ''` lints clean and is a parse error under 5.6. The
  real defect was in `lib/dump_one.php` and every documented gate passed while
  the `dump` subcommand failed on every input.
- **ruff reports no rule, at any rule selection, for a 3.9+ API already in the
  code at `target-version = "py38"`.** `target-version` stops ruff from
  *recommending* 3.9+ APIs — FURB188 fires on a 3.8-safe slice under `py39` and
  is silent under `py38` — but it does not flag existing misuse. The real
  defect was `str.removesuffix()` in `lib/extract_pools.py` under a 3.8+ claim.

Both gates were verified by reintroduction: reintroduce the construct and the
test fails.

Both are deliberately blunt. A false positive costs a comment rewrite; a false
negative costs a broken run. `test_php56_syntax.py` strips comments and string
literals before scanning, so documenting the constraint does not trip it.

## Integration gate

Two tiers. See `tests/integration/README.md`.

```bash
export IONCUBE_STRIP_PHP56=/usr/local/bin/php5.6
export IONCUBE_STRIP_INI=/etc/php56/php.ini
export IONCUBE_STRIP_ARM56=/usr/local/lib/arm56.so
export IONCUBE_STRIP_CORPUS=/path/to/encrypted/tree   # optional
python3 -m pytest tests/integration -v -rs
```

**Not in CI**, because it needs PHP 5.6, the ionCube Loader, and an encrypted
corpus that must not be committed. The CI workflow counts skipped tests and
fails if the count is zero, so a green badge can never be mistaken for "the
pipeline works".

## Verifying a gate still bites

Do this after touching any gate, not just once:

```bash
cp bin/ioncube-strip /tmp/cli.bak
printf '\nfoo() {\n  local x=$1\n  echo $x\n}\n' >> bin/ioncube-strip
make check            # must exit non-zero
cp /tmp/cli.bak bin/ioncube-strip
```

Two traps found the hard way:

- Do not add `# shellcheck disable=` to the probe. It suppresses the rule you
  are trying to trigger and the gate looks fine.
- `bin/ioncube-strip` sets `set -euo pipefail`, which makes shellcheck suppress
  SC2164. A `cd` probe therefore yields a false pass. Use an unquoted
  expansion (SC2086) instead.

## Pre-release

All blockers above green on `main`, plus the pre-release list in
`docs/CHECKLIST.md`. `v1.0.0` is additionally blocked on `docs/ROADMAP.md` T017:
the headline capability has to be settled before a 1.0 claim is made.
