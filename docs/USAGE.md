# ioncube-strip — Usage Guide

## Overview

`ioncube-strip` has four subcommands:

| Command | Purpose | Requires PHP 5.6 + arm56 |
|---------|---------|---------------------------|
| `scan`  | Find encrypted files | No |
| `dump`  | Execute files to produce dumps | **Yes** |
| `pool`  | Extract literal pools from dumps | No |
| `run`   | Full pipeline (scan → dump → pool) | **Yes** |

## Global Options

| Option | Description |
|--------|-------------|
| `--config FILE` | Configuration file (default: `config/ioncube-strip.yaml.example`) |
| `--dry-run` | Show commands without executing |
| `--verbose` | Verbose output |
| `--help` | Show help for command |
| `--version` | Show version |

## scan — Find Encrypted Files

```bash
ioncube-strip scan --source <dir> [--output <file>] [--config <file>]
```

**Options:**
- `--source DIR` (required) — Directory to scan recursively
- `--output FILE` — Output file for list (default: stdout)

**Output:** Newline-separated absolute paths of encrypted files.

**Example:**
```bash
# Scan and save list
./bin/ioncube-strip scan --source /var/www/encrypted --output encrypted.list

# Scan and pipe to dump
./bin/ioncube-strip scan --source /var/www/encrypted | \
  xargs -I {} ./bin/ioncube-strip dump --source /var/www/encrypted --output /tmp/workdir
```

## dump — Execute Files Under PHP 5.6 + arm56

```bash
ioncube-strip dump --source <dir> --output <dir> [--config <file>] [--jobs N]
```

**Options:**
- `--source DIR` (required) — Source root (same as scan)
- `--output DIR` (required) — Output root for dumps
- `--jobs N` — Parallel jobs (default: 1, **warning**: shared tmp dir)
- `--config FILE` — Config file

**Process:**
1. Runs `scan` internally to get file list
2. For each file: executes under PHP 5.6 + arm56
3. Collects arm56 output to `output/dumps/` (mirrored structure)
4. Logs errors to `output/dump_errors.log`

**Example:**
```bash
# Full dump
./bin/ioncube-strip dump --source /var/www/encrypted --output /tmp/workdir

# With custom config
./bin/ioncube-strip dump --source /var/www/encrypted --output /tmp/workdir --config ./myconfig.yaml

# Dry run to see commands
./bin/ioncube-strip dump --source /var/www/encrypted --output /tmp/workdir --dry-run
```

## pool — Extract Literal Pools

```bash
ioncube-strip pool --dumps <dir> --output <dir> [--config <file>]
```

**Options:**
- `--dumps DIR` (required) — Directory containing dump files (from `dump` command)
- `--output DIR` (required) — Output root for pools
- `--config FILE` — Config file

**Process:**
1. Discovers all `*.fn.*` files under dumps directory
2. Groups by function name
3. Extracts ASCII runs from hex dumps
4. Deduplicates per function (first appearance wins)
5. Writes `pools/<func>.txt` and `pools/_index.json`

**Example:**
```bash
# Extract pools
./bin/ioncube-strip pool --dumps /tmp/workdir/dumps --output /tmp/workdir

# View results
cat /tmp/workdir/pools/myFunction.txt
cat /tmp/workdir/pools/_index.json | jq .
```

## run — Full Pipeline

```bash
ioncube-strip run --source <dir> --output <dir> [--config <file>] [--jobs N]
```

**Options:**
- `--source DIR` (required) — Source root with encrypted files
- `--output DIR` (required) — Output root for all artifacts
- `--jobs N` — Parallel dump jobs (default: 1)
- `--config FILE` — Config file

**Example:**
```bash
# Complete pipeline
./bin/ioncube-strip run --source /var/www/encrypted --output /tmp/workdir

# With verbose output
./bin/ioncube-strip run --source /var/www/encrypted --output /tmp/workdir --verbose
```

## Configuration

All options can be set in `ioncube-strip.yaml` (see [CONFIGURATION.md](CONFIGURATION.md)).

Environment variables override config:
```bash
export PHP56=/custom/php5.6
export PHP56_INI=/custom/php.ini
export ARM56_SO=/custom/arm56.so
export ARM56_TMP=/custom/tmp
```

## Working with Large Codebases

### Incremental Processing

```bash
# 1. Scan once
./bin/ioncube-strip scan --source /big/codebase --output all_files.list

# 2. Process in batches
split -l 100 all_files.list batch_
for batch in batch_*; do
  ./bin/ioncube-strip dump --source /big/codebase --output /tmp/workdir < "$batch"
done

# 3. Extract pools once
./bin/ioncube-strip pool --dumps /tmp/workdir/dumps --output /tmp/workdir
```

### Resume After Failure

```bash
# dump_errors.log contains failed files
cat /tmp/workdir/dump_errors.log

# Re-run dump on failed files only
./bin/ioncube-strip dump --source /big/codebase --output /tmp/workdir \
  --config <(grep -v "ERROR" /tmp/workdir/dump_errors.log | cut -d: -f1)
```

## Output Interpretation

### Pool Files (`pools/<func>.txt`)

Each line is a deduplicated ASCII string from the function's literal buffer.
Order = first appearance across all dump variants.

Typical contents:
- Function/method names called
- Class names instantiated
- Error/exception messages
- SQL queries (or fragments)
- Configuration keys
- File paths
- Constant values

### Index File (`pools/_index.json`)

```json
{
  "myFunction": {
    "variants": 3,
    "raw_bytes": 32768,
    "runs": 47
  }
}
```
- `variants`: Number of dump files for this function
- `raw_bytes`: Total bytes across all variants
- `runs`: Unique ASCII strings extracted

## Common Workflows

### Recovery Workflow

```bash
# 1. Full pipeline
./bin/ioncube-strip run --source /encrypted/app --output /recovery/work

# 2. Examine pools
ls /recovery/work/pools/*.txt

# 3. Pick a function to reconstruct
cat /recovery/work/pools/db_query.txt
# Output shows: "SELECT * FROM users WHERE id = ?", "mysqli_query", "fetch_assoc"

# 4. Write PHP 8.x implementation manually
# 5. Test against original behavior
```

### Verification Workflow

```bash
# Check if specific function was captured
grep -l "mysqli_query" /recovery/work/pools/*.txt

# Compare pool sizes
wc -l /recovery/work/pools/*.txt | sort -n

# Find functions with SQL
grep -l "SELECT\|INSERT\|UPDATE\|DELETE" /recovery/work/pools/*.txt
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage error / invalid arguments |
| 2 | Runtime error (missing toolchain, execution failure) |
| 3 | Configuration error |

## Getting Help

```bash
# General help
./bin/ioncube-strip --help

# Command-specific help
./bin/ioncube-strip scan --help
./bin/ioncube-strip dump --help
./bin/ioncube-strip pool --help
./bin/ioncube-strip run --help
```