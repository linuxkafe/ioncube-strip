# ioncube-strip

**Offline ionCube 5.x literal pool extractor for PHP source recovery**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PHP 5.6](https://img.shields.io/badge/PHP-5.6-8892BF.svg)](https://www.php.net/)

## What it does

`ioncube-strip` helps recover source code from ionCube-encrypted PHP files (v5.x era, PHP 5.0-5.6) by:

1. **Scanning** a codebase for ionCube markers (`_il_exec`, `// 00e5`)
2. **Executing** each encrypted file under PHP 5.6 with the `arm56` extension
3. **Collecting** the runtime literal buffer dumps (`RESERVED[3]`)
4. **Extracting** deduplicated printable ASCII strings per function

The output **literal pools** (one file per function) contain the strings the original code *had* to contain — function names, class names, error messages, SQL queries, config keys. These pools are the raw material for **manual source reconstruction**.

## Quick Start

### Prerequisites

- **PHP 5.6 CLI** with development headers
- **arm56 extension** (build from source — see [INSTALL.md](docs/INSTALL.md))
- **Python 3.8+** with PyYAML (`pip install -r requirements.txt`)

### Installation

```bash
git clone https://github.com/yourusername/ioncube-strip.git
cd ioncube-strip
pip install -r requirements.txt
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

### Usage

**Full pipeline (recommended):**

```bash
./bin/ioncube-strip run --source /path/to/encrypted/code --output /path/to/workdir
```

**Individual steps:**

```bash
# 1. Scan for encrypted files
./bin/ioncube-strip scan --source /path/to/encrypted/code --output files.list

# 2. Dump each file (requires PHP 5.6 + arm56)
./bin/ioncube-strip dump --source /path/to/encrypted/code --output /path/to/workdir

# 3. Extract literal pools from dumps
./bin/ioncube-strip pool --dumps /path/to/workdir/dumps --output /path/to/workdir
```

### Output

```
workdir/
├── dumps/                 # Raw arm56 output (mirrored source structure)
│   └── includes/
│       └── functions.php.fn.myFunction_0x1000.txt
└── pools/                 # Extracted literal pools
    ├── myFunction.txt     # Deduplicated ASCII strings
    ├── anotherFunction.txt
    └── _index.json        # Per-function statistics
```

## Documentation

- [Installation Guide](docs/INSTALL.md) — PHP 5.6, arm56 build, troubleshooting
- [Usage Guide](docs/USAGE.md) — All commands, options, examples
- [Configuration](docs/CONFIGURATION.md) — Config file schema, all options
- [Legal Notice](docs/LEGAL.md) — **Read before use**

## How it works

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Scan      │───▶│   Dump      │───▶│  Collect    │───▶│  Extract    │
│  (find)     │    │ (execute)   │    │ (mirror)    │    │  (pools)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     Python            PHP 5.6            Python            Python
  find_encrypted.py  dump_one.php      collect_dumps.py  extract_pools.py
```

The `arm56` extension hooks the ionCube VM at function entry and snapshots the shared literal buffer (`RESERVED[3]`). This buffer contains all string literals used by the function. By running the encrypted file, we trigger these hooks and capture the literals.

## Limitations

- **ionCube 5.x only** — Does not work with ionCube 6.x, 10.x, 12.x
- **Requires PHP 5.6 + arm56** — Not compatible with PHP 7+
- **No decompilation** — Output is literal strings only, no control flow
- **Manual reconstruction required** — Human must write PHP 8.x code from pools
- **Offline only** — No network access, no license server communication

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

## License

MIT License — see [LICENSE](LICENSE) for details.

SPDX-License-Identifier: MIT