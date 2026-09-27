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
| G5 | Tool-free integration tests | `python3 -m pytest tests/integration` | CI |
| G6 | No hardcoded paths | `make check-hardcoded-paths` | CI |
| G7 | No network calls | `make check-network-calls` | CI |
| G8 | No emojis | `make check-emoji` | CI |
| G9 | SPDX headers | `make check-legal-headers` | CI |
| G10 | Config schema | `make validate-config` | CI |
| G11 | **PHP 5.6 syntax floor** | `pytest tests/unit/test_php56_syntax.py` | via G4, CI |
| G12 | **Python 3.8 API floor** | `pytest tests/unit/test_python_floor.py` | via G4, CI |
| G13 | **arm56 generation classification** | `pytest tests/unit/test_probe_arm56.py` | via G4, CI |

`make check` covers G1-G5. G6-G10 run as separate targets so a policy failure
is distinguishable from a lint failure; CI runs all of them.

## Warnings

| ID | Check | Note |
|----|-------|------|
| G14 | `ruff format --check lib/ tests/ scripts/` | Not a blocker. `make format` rewrites in place. |
| G15 | `bash -n bin/ioncube-strip` | Subsumed by G3. |

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
