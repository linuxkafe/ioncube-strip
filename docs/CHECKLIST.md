# ioncube-strip — Pre-commit / Pre-release Checklist

## Pre-commit (Quick — Run on Every Commit)

- [ ] **Tests pass** — `python -m pytest tests/unit -v` (unit tests only)
- [ ] **Python lint clean** — `ruff check lib/ tests/`
- [ ] **Shell lint clean** — `shellcheck bin/ioncube-strip`
- [ ] **PHP lint clean** — `php -l lib/dump_one.php` (and any other .php files)
- [ ] **No hardcoded paths** — `grep -r "/home/" lib/ bin/ config/ ; grep -r "whmcs" lib/ bin/ config/`
- [ ] **No network calls** — `grep -r "http://\|https://\|curl\|wget\|requests\|urllib" lib/ bin/`
- [ ] **No emojis in source** — `grep -r "[\xF0-\xF4][\x80-\xBF]{3}" lib/ bin/ tests/ config/`
- [ ] **Config schema valid** — `python -c "import yaml; yaml.safe_load(open('config/ioncube-strip.yaml.example'))"`
- [ ] **Diffstory written** — Build output includes what changed, why, untouched, risks

## Pre-release (Thorough — Run Before Tagging)

- [ ] **All pre-commit checks pass**
- [ ] **Integration tests documented** — `tests/integration/README.md` explains PHP 5.6 + arm56 requirement
- [ ] **README complete** — Install, usage, config, limitations, legal
- [ ] **INSTALL.md complete** — Prerequisites, arm56 build, PHP 5.6 install
- [ ] **USAGE.md complete** — All subcommands, options, examples
- [ ] **CONFIGURATION.md complete** — All config options with defaults
- [ ] **LEGAL.md reviewed** — No new legal exposure, SPDX headers present
- [ ] **Version bumped** — `VERSION` file, `__version__` in Python, CLI `--version`
- [ ] **CHANGELOG updated** — Since last release
- [ ] **Release artifacts** — Tarball, checksums, signed if possible
- [ ] **GitHub release drafted** — Notes, assets attached

## Code Quality Gates (CI)

| Gate | Command | Blocker? |
|------|---------|----------|
| Python syntax | `python -m py_compile lib/*.py` | Yes |
| Python lint | `ruff check lib/ tests/` | Yes |
| Python types | `mypy lib/` (if configured) | No |
| PHP syntax | `php -l lib/*.php` | Yes |
| Shell syntax | `bash -n bin/ioncube-strip` | Yes |
| Shell lint | `shellcheck bin/ioncube-strip` | Yes |
| Unit tests | `python -m pytest tests/unit -v` | Yes |
| Config validation | `python -c "import yaml, sys; yaml.safe_load(sys.stdin)" < config/ioncube-strip.yaml.example` | Yes |
| No hardcoded paths | Custom script | Yes |
| No network calls | Custom script | Yes |

## Documentation Gates

| Gate | Check | Blocker? |
|------|-------|----------|
| README exists | `test -f README.md` | Yes |
| All CLI commands documented | `grep -c "## " USAGE.md` >= 4 | Yes |
| Config options documented | All YAML keys in CONFIGURATION.md | Yes |
| Legal notice present | `test -f LEGAL.md` | Yes |
| SPDX headers in all source | `head -5 lib/*.py lib/*.php bin/* | grep -c SPDX` == total files | Yes |

## Security Gates

| Gate | Check | Blocker? |
|------|-------|----------|
| No secrets in repo | `git-secrets --scan` (if available) | Yes |
| No eval/exec in Python | `grep -r "eval\|exec\|subprocess.*shell=True" lib/` | Yes |
| No shell injection | `grep -r '\$\(' bin/ | grep -v '\$\('` | Yes |
| Path traversal safe | `grep -r '\.\./' lib/ bin/` | Yes |