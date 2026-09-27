# ioncube-strip — Pre-commit / Pre-release Checklist

Every command below exists and is wired into `make check` or the CI workflow.
If one of these does not, delete the line rather than leaving it aspirational:
a checklist entry pointing at a non-existent gate is worse than no entry.

## Pre-commit (run on every commit)

```bash
make check          # ruff + shellcheck + php -l + unit tests
```

Or individually:

- [ ] **Python lint clean** — `ruff check lib/ tests/ scripts/`
- [ ] **Shell lint clean** — `shellcheck bin/ioncube-strip`
- [ ] **PHP parses** — `php -l lib/dump_one.php`
- [ ] **Unit tests pass** — `python3 -m pytest tests/unit`
- [ ] **Tool-free integration tests pass** — `python3 -m pytest tests/integration`
- [ ] **No hardcoded paths** — `make check-hardcoded-paths`
- [ ] **No network calls** — `make check-network-calls`
- [ ] **No emojis in source** — `make check-emoji`
- [ ] **SPDX headers present** — `make check-legal-headers`
- [ ] **Config schema valid** — `make validate-config`
- [ ] **Diffstory written** — what changed, why, what was untouched, remaining risks

### Gates that must be able to fail

Verify a gate is not vacuous before trusting a green run. The historical
defect in this repo was `which shellcheck && shellcheck X || echo "not
installed"` — the `||` fired on *any* non-zero exit, so real findings were
swallowed while the gate printed "All checks passed".

```bash
# Inject a finding, confirm the gate goes red, then revert.
cp bin/ioncube-strip /tmp/cli.bak
printf '\nfoo() {\n  local x=$1\n  echo $x\n}\n' >> bin/ioncube-strip
make check            # must exit non-zero
cp /tmp/cli.bak bin/ioncube-strip
```

Note that `set -euo pipefail` at the top of `bin/ioncube-strip` suppresses
SC2164, so a `cd` probe will look like a pass. Use an unquoted expansion
(SC2086) instead.

## Pre-release (run before tagging)

- [ ] All pre-commit checks pass
- [ ] `docs/LEGAL.md` reviewed — it asserts what is and is not included, and
      that statement is now false in one place whenever arm56 changes
- [ ] README, INSTALL, USAGE, CONFIGURATION consistent with the code
- [ ] Version bumped in `bin/ioncube-strip` (`VERSION=`), the single source of
      truth. There is no `VERSION` file and no `__version__` in the Python
      modules; do not add a checklist item for either
- [ ] `docs/ROADMAP.md` statuses reconciled against the tree, not against intent
- [ ] `aes/kanban.md` current state updated
- [ ] `tests/integration/README.md` still describes the tiers accurately
- [ ] Integration tier run with the toolchain **if one is available** — and if
      it was not, say so in the release notes rather than implying a pass
- [ ] Release artifacts: tarball, checksums
- [ ] `make release` then `make verify-release`

## What CI cannot check

Stated so nobody reads a green CI badge as more than it is:

| Not checked in CI | Why | Where it is checked instead |
|---|---|---|
| PHP 5.6 syntax floor | `php -l` on 8.x accepts 7.0+ syntax | `tests/unit/test_php56_syntax.py` (runs in CI) |
| Python 3.9+ API use | ruff reports no rule for it at `target-version = py38` | `tests/unit/test_python_floor.py` (runs in CI) |
| Extraction against real input | needs PHP 5.6, the Loader, and a corpus none of which may be committed | `tests/integration/test_extraction.py`, run manually |
| arm56 build from `arm56/` | needs PHP 5.6 headers | `docs/INSTALL.md`, manual |
| The legacy pool path end to end | needs the legacy extension | `docs/ROADMAP.md` T017 |

The first two *are* checked in CI, by tests rather than by linters. The last
three are genuine gaps.
