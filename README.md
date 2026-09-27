# ioncube-strip

**Offline recovery of class shape from ionCube 5.x encrypted PHP files**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PHP 5.6](https://img.shields.io/badge/PHP-5.6-8892BF.svg)](https://www.php.net/)

## What it does

`ioncube-strip` recovers the *shape* of ionCube-encrypted PHP files (v5.x era, PHP 5.0-5.6):

1. **Scanning** a codebase for ionCube markers (`_il_exec`, `// 00e5`)
2. **Loading** each encrypted file under PHP 5.6 with the ionCube Loader
3. **Reporting** what the Loader itself resolved: parent class, interfaces,
   constants, properties, method signatures, and per-method literal *counts*
   (`manifest`, `symbols`)
4. **Extracting** literal pool strings — available only with the legacy arm56
   build (`dump`, `pool`), see below

The manifest is the primary evidence for reconstructing a class. While a file
is still encrypted the Loader must resolve its inheritance in order to load it,
so the parent and interfaces it reports are the true ones, not inferred.

### Two capabilities, not equally supported

| Capability | Stages | Needs |
|---|---|---|
| Class shape, method signatures, literal counts | `manifest`, `symbols` | the in-tree v4 extension (`arm56/arm56.c`) |
| Literal pool strings | `dump`, `pool` | the **legacy** arm56 build, which is not in this repo |

The in-tree extension writes JSON and cannot feed the pool extractor. The
legacy pool path also carries an open question: our own findings record that
the Loader frees the literal pool once a body has run and
`op_array->reserved[3]` is NULL for encoded code, which would mean pool
*content* is unrecoverable in principle. Read
[docs/CONFIGURATION.md](docs/CONFIGURATION.md) ("Two arm56 generations") before
relying on it.

**Neither capability recovers method bodies.** Bodies require executing the code
with the original toolchain present, or reconstructing from signatures and
domain knowledge.

## Quick Start

### Prerequisites

- **PHP 5.6 CLI** with development headers
- **arm56 v4 extension** (source is in `arm56/` — see [INSTALL.md](docs/INSTALL.md))
- **Python 3.8+** with PyYAML (`pip install -r requirements.txt`)

### Installation

```bash
git clone https://github.com/yourusername/ioncube-strip.git
cd ioncube-strip
pip install -r requirements.txt

# Build the extension against your PHP 5.6
cd arm56 && phpize && ./configure && make && sudo make install && cd ..
```

### Configuration

Copy the example config and customize paths:

```bash
cp config/ioncube-strip.yaml.example ioncube-strip.yaml
# Edit ioncube-strip.yaml with your PHP 5.6 and arm56 paths
```

Or use environment variables:

```bash
export PHP56=/path/to/php5.6
export PHP56_INI=/path/to/php56.ini
export ARM56_SO=/path/to/arm56.so
```

Check which arm56 generation you actually have:

```bash
python3 lib/probe_arm56.py --config config/ioncube-strip.yaml.example
```

### Usage

**Class shape (works with the in-tree extension):**

```bash
# 1. Scan for encrypted files
./bin/ioncube-strip scan --source /path/to/encrypted/code --output files.list

# 2. Reflection manifests — parent, interfaces, signatures
./bin/ioncube-strip manifest --files files.list --output manifests/

# 3. arm56 symbol dumps — literal counts, opcodes
./bin/ioncube-strip symbols --files files.list --output symbols/
```

**Literal pools (needs the legacy arm56 build):**

```bash
./bin/ioncube-strip dump --source /path/to/encrypted/code --output /path/to/workdir
./bin/ioncube-strip pool --dumps /path/to/workdir/dumps --output /path/to/workdir
```

### Output

```
manifests/
├── _manifest_report.json    # per-file status, learned stub symbols
└── _<sanitized_path>.manifest.json   # parent, interfaces, constants,
                                       # properties, method signatures

symbols/
├── _batch_report.json       # per-file status and counts
└── _<sanitized_path>.json   # symbols, literal counts, opcodes

workdir/                    # legacy pool path only
├── dumps/                  # raw arm56 hex output
└── pools/                  # deduplicated ASCII strings per function
    ├── myFunction.txt
    └── _index.json
```

## Documentation

- [Installation Guide](docs/INSTALL.md) — PHP 5.6, arm56 build, troubleshooting
- [Usage Guide](docs/USAGE.md) — All commands, options, examples
- [Configuration](docs/CONFIGURATION.md) — Config schema, the two arm56 generations
- [Legal Notice](docs/LEGAL.md) — **Read before use**

## How it works

Two independent mechanisms read the same encrypted files:

```
manifest/  encrypted.php ─▶ PHP 5.6 + ionCube Loader ─▶ Reflection
             The Loader must resolve inheritance to load the file, so the
             parent, interfaces and signatures are the real ones.

symbols/   encrypted.php ─▶ PHP 5.6 + Loader + arm56 v4 ─▶ JSON op_array
             arm56 (arm56/arm56.c) wraps zend_compile_file and serialises the
             op_array the Loader materialises, including literal counts.
```

They share nothing but the file list, which is what makes their agreement
meaningful: the integration suite cross-checks the method count between them
and treats a disagreement as a defect signal. See
[docs/CONFIGURATION.md](docs/CONFIGURATION.md) ("Cross-check").

The legacy pool path worked differently — the original arm56 hooked function
entry and snapshotted `RESERVED[3]`, and `extract_pools.py` parsed the hex
dumps it wrote. That extension is not in this repository.

## Limitations

- **ionCube 5.x only** — Does not work with ionCube 6.x, 10.x, 12.x
- **Requires PHP 5.6** — Not compatible with PHP 7+
- **Shape, not bodies** — Signatures and counts only; no control flow, no decompilation
- **Pool path needs an external extension** — and may have nothing to produce
- **Manual reconstruction required** — Human must write the PHP from signatures
- **Offline only** — No network access, no license server communication

## Testing

```bash
make check                     # lint + unit tests, no toolchain needed
python3 -m pytest tests/integration -v
```

The integration suite has two tiers. The tool-free tier always runs. The
toolchain/corpus tier skips unless `IONCUBE_STRIP_PHP56`, `IONCUBE_STRIP_INI`,
`IONCUBE_STRIP_ARM56` and `IONCUBE_STRIP_CORPUS` are set. **A run where those
skip is not a pass** — it means the tool-free paths passed and the pipeline was
never exercised on real input.

## Legal

**Read [LEGAL.md](docs/LEGAL.md) before using.**

This tool is for **legitimate recovery** of:
- Abandoned software you have a license for
- Software whose license server has been shut down
- Digital preservation of cultural heritage
- Authorized security research

**Do NOT use for:**
- Circumventing active license enforcement
- Unauthorized access to proprietary systems
- Redistributing recovered code without permission

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run `make check` (lint + tests)
4. Submit a pull request

Two version floors are enforced by tests, not by the linter: every shipped
`.php` file must parse under PHP 5.6 (`tests/unit/test_php56_syntax.py`) and
`lib/` must avoid 3.9+ APIs (`tests/unit/test_python_floor.py`).

## License

MIT License — see [LICENSE](LICENSE) for details.

SPDX-License-Identifier: MIT