# ioncube-strip

**Recover the class structure of ionCube 5.x encrypted PHP files — offline, with nothing but a PHP 5.6 runtime.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PHP 5.6](https://img.shields.io/badge/PHP-5.6-8892BF.svg)](https://www.php.net/)

---

## Read this first

This tool recovers **declarations**, not **behaviour**. That distinction is the
whole story, and it is not a limitation of this implementation.

- **You get**, for every class the tool can load: the true parent class,
  interface list, abstract/final flags, constants, properties, and every method
  signature with visibility, static/abstract, and parameter names and types.
  Doc comments survive encryption too, so `@param` and `@return` types come
  back as well.
- **You do not get**: a single method body. Not one conditional, query, loop or
  calculation. They are not hidden from this tool — they are not present in the
  runtime at all. `arm56` reports `content_faulted` and `num_ops: 0` for every
  encoded method, which is the extension's own account of what it found.

If you need working code, this tool hands you a correct API map and you still
have to write the implementation. That is a large job, made smaller by not
having to guess the API. If you need to *decompile*, this is the wrong tool and
no version of it will be the right one.

Roughly one encrypted file in three cannot be read even for declarations — see
[Where it does not work](#where-it-does-not-work). That is stated up front
because a tool that only tells you what it can do is worth more than one that
surprises you later.

## Measured on WHMCS 5.3.12

PHP 5.6.40, ionCube Loader `ionCube24`, `arm56` v4, 516 encrypted files:

| | |
|---|---|
| Classes recovered | 162 |
| **Declaration fidelity** | **162 / 162 identical to the encrypted original** |
| Generated skeletons that parse and load under PHP 5.6 | 143 / 143 |
| Method declarations | 1437 |
| Property declarations | 550 |
| Constant declarations | 104 |
| Encrypted PHP read | 7,167,567 bytes |
| Skeleton PHP produced | 7,526 lines |
| **Method bodies recovered** | **0** |
| Wall clock, full corpus | ~5 s on 4 jobs |

"Fidelity" means this: the encrypted original and a generated skeleton were
reflected in separate PHP 5.6 processes and the facts diffed — parent, interface
list, `abstract`, `final`, constants, own properties, own method signatures
including parameter names. Not one difference. Full accounting, including what
was tried and did not work, is in
[`docs/VALIDATION.md`](docs/VALIDATION.md).

## How it works

Two independent mechanisms read the same encrypted files and share nothing but
the file list:

```
manifest/   encrypted.php ─▶ PHP 5.6 + ionCube Loader ─▶ Reflection
              The Loader must resolve inheritance to load the file, so the
              parent and interfaces it reports are the real ones.

symbols/    encrypted.php ─▶ PHP 5.6 + Loader + arm56 v4 ─▶ JSON op_array
              arm56 wraps zend_compile_file and serialises the op_array the
              Loader materialises: literal counts, opcodes, signatures.
```

Because they are independent, their agreement is evidence. The test suite
cross-checks them: class name lists must match for every file, and for a class
with no parent and no interfaces — where both tools are counting the same
quantity — the method counts must match exactly. On WHMCS that is 167 files and
118 of 118 classes. A disagreement is a defect signal, not noise.

Encrypted library files reference classes living in *other* encrypted files,
and the Loader raises an ordinary PHP fatal when one is missing. A fatal cannot
be caught, so each attempt runs in its own process; the missing symbol names are
learned from stderr and pre-declared as empty stubs of the right kind, and the
run repeats until the set stops growing. On WHMCS that converges in three
rounds, learning 30 symbols.

## Requirements

- **PHP 5.6 CLI** with development headers. Not 7+. The ionCube Loader is a
  5.x-era `zend_extension` and will not load otherwise.
- **The ionCube Loader for PHP 5.6** — not included here, and you must be
  entitled to it.
- **arm56 v4** — source is in [`arm56/`](arm56), MIT, first-party. Build it
  yourself against your PHP 5.6.
- **Python 3.8+** with PyYAML.

### The ini, which is the part people get wrong

The Loader must be the **first** `zend_extension` or it aborts. A stock Debian
php.ini loads opcache as a `zend_extension` at priority 10 and will conflict, so
use a dedicated ini:

```ini
zend_extension=/path/to/ioncube_loader_lin_5.6.so
extension=json.so
error_reporting = E_ALL
display_errors = stderr
```

Note `arm56` loads with `extension=`, **not** `zend_extension=`. It declares a
plain `zend_module_entry`; loaded the other way PHP reports *"doesn't appear to
be a valid Zend extension"* and every `arm56_*` function is simply absent — a
wrong answer rather than an error.

## Install

```bash
git clone https://github.com/linuxkafe/ioncube-strip.git
cd ioncube-strip
pip install -r requirements.txt

# Build arm56 against your PHP 5.6
cd arm56
autoreconf                     # only if config.m4 changed
phpize
./configure --with-php-config=/usr/bin/php-config5.6
make
sudo make install
cd ..
```

`arm56/configure.in` and `arm56/config.h.in` are not tracked — they are
regenerated by `autoconf`. Only `arm56.c` and `config.m4` are committed, and no
build artifact ever is.

### Configuration

```bash
cp config/ioncube-strip.yaml.example ioncube-strip.yaml
# edit with your paths
```

Or use environment variables, which **override** the config file:

```bash
export PHP56=/usr/bin/php5.6
export PHP56_INI=/path/to/php56-ioncube.ini
export ARM56_SO=/usr/local/lib/arm56.so
export PHP56_EXTRA=/path/to/json.so   # only if the 5.6 build lacks json_encode
```

Check which arm56 you actually have before anything else:

```bash
python3 lib/probe_arm56.py --config config/ioncube-strip.yaml.example
# v4:  arm56 generation: v4 (4.0.0-spike)
```

## Usage

```bash
# 1. Scan for encrypted files
./bin/ioncube-strip scan --source /path/to/encrypted --output files.list

# 2. Class shape: parent, interfaces, constants, properties, signatures
./bin/ioncube-strip manifest --files files.list --output manifests --jobs 4

# 3. arm56 symbols: literal counts, opcodes
./bin/ioncube-strip symbols  --files files.list --output symbols  --jobs 4
```

`--verbose` reports the resolved toolchain, the arm56 generation and the counts
behind the run, on stderr so stdout stays a clean list. `--dry-run` prints what
would be executed and creates nothing.

Full reference: [`docs/USAGE.md`](docs/USAGE.md).

### Output

```
manifests/
├── _manifest_report.json              per-file status, learned stub symbols
└── _<sanitized_path>.manifest.json    parent, interfaces, constants,
                                       properties, method signatures

symbols/
├── _batch_report.json                 per-file status and counts
└── _<sanitized_path>.json             symbols, literal counts, opcodes
```

### A note on the legacy `dump` / `pool` stages

`dump`, `pool` and `run` are the original literal-pool pipeline. They consume
the *legacy* arm56 hex-dump format, which the extension in this repository does
not produce — it writes JSON. Against the in-tree extension they would collect
nothing, so `dump` refuses to start rather than reporting an empty success.

The legacy extension is not in this repository, and `docs/VALIDATION.md` records
the finding that literal pool *content* is unrecoverable in principle with this
toolchain. The code is kept because it is written and tested, but **no part of
this project claims it works**, and nothing in the documentation advertises it.
See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md), "Two arm56 generations".

## Where it does not work

On the full 516-file WHMCS corpus, 167 files yield class shape. The 349 that do
not, by cause:

| Count | Cause |
|---|---|
| 173 | The file calls `exit`/`die` at include time. Sampled 40: **none declared a class**, so there was nothing to recover |
| 94 | `require '../init.php'` — needs a live application and database |
| 60 | Needs globals (`$whmcs`) or an undefined method |
| 22 | Parse errors and other fatals under PHP 5.6 |

A fake bootstrap was tried for the 154 that appear to need an application —
fake config, stubbed database functions. It does not help: those files need a
real database, and the API endpoints additionally carry a direct-access guard
that exits before any declaration is reached. It is not defeated by `ROOTDIR`,
`REQUEST_URI` or `IN_API`.

None of these are class-definition files. That is the category this method can
read, and 162 classes is what WHMCS has.

## Testing

```bash
make check                          # lint + unit + every policy gate
python3 -m pytest tests/unit -q     # no toolchain needed
python3 -m pytest tests/integration -q
```

The integration suite has two tiers. The **tool-free** tier always runs. The
**toolchain/corpus** tier skips unless `IONCUBE_STRIP_PHP56`,
`IONCUBE_STRIP_INI`, `IONCUBE_STRIP_ARM56` and `IONCUBE_STRIP_CORPUS` are set.

**A run where those skip is not a pass.** It means the tool-free paths passed
and the pipeline was never exercised on real input. With the toolchain and
corpus set, the full suite is 76 passed, 0 skipped; without, 68 passed and 8
skipped with every reason printed.

No encrypted fixture is committed, ever — a fixture containing ionCube-encoded
third-party code is a legal liability. The corpus is always supplied from
outside the repository.

Quality gates and how to verify they still bite:
[`docs/QUALITY_GATES.md`](docs/QUALITY_GATES.md).

## Limitations

- **ionCube 5.x only.** Not 6.x, 10.x or 12.x.
- **PHP 5.6 only.** The Loader will not load on 7+.
- **Declarations, not behaviour.** See the top of this file.
- **One loader generation tested** (`ionCube24`), one patchlevel, one corpus.
- **Roughly a third of files are unreadable**, and not for want of trying.
- **Offline only.** No network access at any stage, by design.

## Legal

**Read [`docs/LEGAL.md`](docs/LEGAL.md) before using this.** It is not legal
advice.

This tool is for recovering software you already hold a licence to: abandoned
installations whose vendor and licence server are gone, and digital
preservation. ionCube encryption is a technical protection measure under DMCA
1201 and EUCD Art. 6, and circumvention may be unlawful in your jurisdiction
even for interoperability. The exemptions that exist are narrow and
fact-specific. Consult a qualified attorney before using this on code you do not
own or have explicit rights to.

This repository contains no ionCube Loader, no decoder, no PHP 5.6 binary and no
encrypted PHP files. The `arm56` extension here is first-party MIT source
written for this project; the *legacy* arm56 extension it replaced is not
included, and its licensing is your responsibility.

## Contributing

```bash
make check              # must pass; the gates are real, verify them
```

Two version floors are enforced by tests, not by the linter, because the
obvious tool cannot see either: every shipped `.php` file must parse under
PHP 5.6 (`tests/unit/test_php56_syntax.py`) and `lib/` must avoid 3.9+ APIs
(`tests/unit/test_python_floor.py`). A contributor who only runs `php -l` on
8.4 will not catch a 7.0 construct, and that is a bug that reaches production.

If you add a gate, verify it fails when it should. A gate that cannot fail is
worse than no gate — this project shipped three of them before they were found.

## Documentation

| | |
|---|---|
| [INSTALL.md](docs/INSTALL.md) | PHP 5.6, arm56 build, troubleshooting |
| [USAGE.md](docs/USAGE.md) | All subcommands, options, examples |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Config schema, the two arm56 generations |
| [VALIDATION.md](docs/VALIDATION.md) | Measured results on WHMCS, and what was tried and failed |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md) | Functional and non-functional requirements |
| [ROADMAP.md](docs/ROADMAP.md) | What is done, what is open, what was measured away |
| [QUALITY_GATES.md](docs/QUALITY_GATES.md) | Every gate, and how to verify it bites |
| [LEGAL.md](docs/LEGAL.md) | Legal notice — read first |

## License

MIT — see [LICENSE](LICENSE).

SPDX-License-Identifier: MIT
