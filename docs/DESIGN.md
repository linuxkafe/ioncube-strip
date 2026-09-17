# ioncube-strip — Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        ioncube-strip CLI                        │
│                         (bin/ioncube-strip)                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│    scan       │  │    dump       │  │    pool       │
│ (subcommand)  │  │ (subcommand)  │  │ (subcommand)  │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│find_encrypted.│  │  dump_one.php │  │extract_pools. │
│      py       │  │ (PHP 5.6)     │  │      py       │
└───────────────┘  └───────────────┘  └───────────────┘
        │                  │                  │
        │                  ▼                  │
        │         ┌───────────────┐           │
        │         │ collect_dumps │           │
        │         │     .py       │           │
        │         └───────────────┘           │
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                  ┌───────────────┐
                  │  Output Dir   │
                  │ dumps/ pools/ │
                  └───────────────┘
```

## Component Specifications

### 1. find_encrypted.py — Scanner

**Input:** Source directory (arg), config (markers)

**Output:** Newline-separated absolute paths to stdout

**Algorithm:**
- Recursive directory walk (os.walk or RecursiveDirectoryIterator)
- For each `.php` file: read first 200KB
- Check each configured marker pattern (default: `_il_exec`, `// 00e5`)
- Print path if any marker matches

**Config:**
```yaml
markers:
  - pattern: "_il_exec"
    type: "substring"
  - pattern: "^//\\s*00e5"
    type: "regex"
```

**Error handling:** Skip unreadable files (log to stderr), continue.

### 2. dump_one.php — Single File Executor

**Input:** File path (argv[1])

**Behavior:**
- Include the file (triggers arm56 hooks on function entry)
- No output, no logic — arm56 writes to `/tmp/arm56_output/`

**Requirements:**
- Must run under PHP 5.6 CLI
- Must have `extension=arm56.so` loaded
- No dependencies, no autoloaders

### 3. collect_dumps.py — Dump Collector

**Input:** Source root, file path, output root, temp dump dir (`/tmp/arm56_output`)

**Behavior:**
- Compute relative path of file from source root
- Find all dump files in temp dir matching the file
- Copy to `output_root/dumps/<relative_path>.fn.*`
- Clean temp dir after copy (or use unique temp per file)

**Matching logic:** arm56 produces files like `_<abs_path_with_underscores>.fn.<func>_0x<addr>.txt`

### 4. extract_pools.py — Pool Extractor

**Input:** Dumps directory, output directory, config

**Algorithm:**
1. Discover all `.fn.*` files recursively
2. Extract function names from filenames (between `.fn.` and `_0x` or `.txt`)
3. For each unique function name:
   - Find all variant dump files
   - Parse hex lines: `^  [0-9a-f]{4,8}: ((?:[0-9a-f]{2} )+)`
   - Convert to raw bytes
   - Extract ASCII runs: `[\x20-\x7e]{minlen,}` (configurable minlen, charset)
   - Deduplicate preserving order (first appearance wins)
   - Filter by max length (configurable, default 2000)
   - Write to `output/pools/<func>.txt`
4. Write `_index.json` with per-function stats

**Parallelism:** ProcessPoolExecutor with configurable worker count (default: CPU count)

**Config:**
```yaml
extraction:
  min_run_length: 3
  max_run_length: 2000
  charset: "ascii"  # or "utf-8"
  workers: 0  # 0 = auto (CPU count)
```

### 5. ioncube-strip (CLI Driver)

**Language:** Bash (POSIX-compliant where possible)

**Subcommands:**
- `scan --source DIR [--config FILE] [--output FILE]`
- `dump --source DIR --output DIR [--config FILE] [--jobs N]`
- `pool --dumps DIR --output DIR [--config FILE]`
- `run --source DIR --output DIR [--config FILE] [--jobs N]` (full pipeline)

**Global options:**
- `--config FILE` — Configuration file
- `--dry-run` — Show commands without executing
- `--verbose` — Debug output
- `--version` — Print version
- `--help` — Usage

**Environment variable overrides:**
- `PHP56` — PHP 5.6 binary
- `PHP56_INI` — PHP 5.6 ini file
- `ARM56_SO` — arm56.so path
- `ARM56_TMP` — arm56 output directory (default: `/tmp/arm56_output`)

## Configuration Schema

```yaml
# ioncube-strip.yaml
toolchain:
  php56: "/usr/local/bin/php5.6"      # PHP 5.6 CLI binary
  php56_ini: "/etc/php56/php.ini"     # PHP 5.6 ini file
  arm56_so: "/usr/local/lib/arm56.so" # arm56 extension
  arm56_tmp: "/tmp/arm56_output"      # arm56 output directory

markers:
  - pattern: "_il_exec"
    type: "substring"
  - pattern: "^//\\s*00e5"
    type: "regex"

output:
  dumps_dir: "dumps"      # Relative to output root
  pools_dir: "pools"      # Relative to output root
  index_file: "_index.json"

extraction:
  min_run_length: 3
  max_run_length: 2000
  charset: "ascii"
  workers: 0

parallelism:
  dump_jobs: 1      # Sequential by default (shared /tmp)
  pool_workers: 0   # 0 = auto
```

## Data Flow

```
Source Tree (encrypted PHP)
        │
        ▼
┌───────────────────┐
│  find_encrypted   │ ──► [file1.php, file2.php, ...]
└───────────────────┘
        │
        ▼ (for each file)
┌───────────────────┐
│   dump_one.php    │ ──► /tmp/arm56_output/_<path>.fn.<func>_0x*.txt
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  collect_dumps    │ ──► dumps/<rel_path>.fn.<func>_0x*.txt
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  extract_pools    │ ──► pools/<func>.txt + pools/_index.json
└───────────────────┘
```

## Error Handling Strategy

| Stage | Failure Mode | Behavior |
|-------|--------------|----------|
| Scan | Unreadable file | Log warning, continue |
| Scan | No files found | Exit 0, empty output |
| Dump | PHP 5.6 not found | Exit 2, clear error |
| Dump | arm56.so not found | Exit 2, clear error |
| Dump | File execution fails | Log error, continue (configurable) |
| Collect | No dumps produced | Log warning, continue |
| Extract | No dump files | Exit 0, empty pools |
| Extract | Parse error in dump | Log warning, skip file |

## Testing Strategy

### Unit Tests (no external deps)
- `find_encrypted`: Fixture files with/without markers
- `extract_pools`: Synthetic arm56 hex output → expected pools
- `config`: Valid/invalid YAML, schema validation
- `CLI`: Argument parsing, subcommand dispatch

### Integration Tests (require PHP 5.6 + arm56)
- Full pipeline on known encrypted file
- Config override verification
- Output structure verification

### Test Fixtures
- **Synthetic only** — No real encrypted code in repo
- Generated by test scripts (hex dumps, marker files)