# ioncube-strip — Usage Guide

## Overview

`ioncube-strip` has six subcommands, in two groups.

| Command | Purpose | Needs PHP 5.6 | Needs arm56 | arm56 generation |
|---------|---------|---------------|-------------|------------------|
| `scan`  | Find encrypted files | No | No | — |
| `manifest` | Reflection class manifests | **Yes** | No | — |
| `symbols`  | Symbol dumps, literal counts | **Yes** | **Yes** | v4 (in this repo) |
| `dump`  | Legacy literal-pool dump | **Yes** | **Yes** | legacy (not in this repo) |
| `pool`  | Extract literal pools from legacy hex dumps | No | No | — |
| `run`   | Legacy pool pipeline (scan → dump → pool) | **Yes** | **Yes** | legacy (not in this repo) |

**Read this before assuming a command works.** `manifest` and `symbols` are the
supported path and work with the extension in this repository. `dump`, `pool`
and `run` consume the *legacy* arm56 hex-dump format, which the in-tree
extension does not produce — it writes JSON. Those three commands are kept
because the code is written and tested, but they need a legacy build and may
have no output to produce at all.

`docs/CONFIGURATION.md` ("Two arm56 generations") has the full comparison.
`python3 lib/probe_arm56.py` tells you which one is loaded.

## Global Options

| Option | Description |
|--------|-------------|
| `--config FILE` | Configuration file (default: `config/ioncube-strip.yaml.example`) |
| `--dry-run` | Print the commands that would run and execute nothing. Creates no output |
| `--verbose` | Report the resolved configuration and the counts behind the run on **stderr** |
| `--help` | Show help for command |
| `--version` | Show version |

`--verbose` writes to stderr, so `scan --output list --verbose` still gives you
a clean file list on stdout. It exists because every subcommand accepts it: a
flag that silently does nothing is worse than no flag, since it advertises a
diagnostic you cannot get.

What `--verbose` adds per stage:

| Stage | Reports |
|---|---|
| `scan` | the source and config in use, and how many paths were written |
| `dump` | resolved `PHP56` / `PHP56_INI` / `ARM56_SO`, the arm56 generation, and the number of dump files produced |
| `pool` | the dumps and output directories, and the number of pool files written |
| `manifest` | resolved toolchain, target count, `jobs`, `rounds`, `timeout` |
| `symbols` | as `manifest`, plus the arm56 generation warning |

## Environment Variables

| Variable | Overrides |
|----------|-----------|
| `PHP56` | `toolchain.php56` |
| `PHP56_INI` | `toolchain.php56_ini` |
| `ARM56_SO` | `toolchain.arm56_so` |
| `ARM56_TMP` | `toolchain.arm56_tmp` (legacy generation only) |
| `PHP56_EXTRA` | `toolchain.php56_extra`; needed by `manifest` if the 5.6 build has no `json_encode` |

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

## manifest — Reflection Class Manifests

```bash
ioncube-strip manifest --files <list> --output <dir> [--source <dir>] [--config <file>]
                       [--jobs N] [--rounds N] [--limit N] [--timeout N]
```

**Options:**
- `--files FILE` (required) — Newline-separated list of target files
- `--output DIR` (required) — Directory for manifests
- `--source DIR` — Base directory for relative paths in the list
- `--config FILE` — Config file
- `--jobs N` — Parallel PHP processes (default: 4)
- `--rounds N` — Max dependency-resolution rounds (default: 8)
- `--limit N` — Process at most N files
- `--timeout N` — Per-file timeout in seconds (default: 30)

**Process:**
1. Runs one PHP 5.6 process per target under the ionCube Loader. arm56 is *not*
   needed — nothing here reads a literal buffer.
2. Encrypted files reference classes in *other* encrypted files, and the Loader
   raises a plain PHP fatal when one is missing. Because a fatal cannot be
   caught, each attempt is its own process. Missing symbol names are learned
   from stderr, pre-declared as empty stubs, and the run repeats until the set
   stops growing.
3. A stub is only ever declared for a symbol no successfully-loaded file has
   provided, so a real class is never shadowed.
4. Reports, per file: parent class, interfaces, constants, properties, method
   signatures with visibility, static/abstract flags and parameter details.

**Output:** one `<sanitized_path>.manifest.json` per target, plus
`_manifest_report.json` with per-file status and the learned stub symbols.

**Example:**
```bash
./bin/ioncube-strip scan --source /var/www/encrypted --output files.list
./bin/ioncube-strip manifest --files files.list --output /tmp/manifests

# 20 files, four at a time
./bin/ioncube-strip manifest --files files.list --output /tmp/manifests \
  --limit 20 --jobs 4
```

## symbols — arm56 Symbol Dumps

```bash
ioncube-strip symbols --files <list> --output <dir> [--source <dir>] [--config <file>]
                      [--jobs N] [--rounds N] [--limit N] [--timeout N]
```

Same options as `manifest`. Runs the same stub-resolution loop, then calls
`arm56_dump()` and records the symbols the Loader registered: per-method
literal counts, opcodes for plain PHP, and signatures for encoded files.

**Requires** the v4 extension (`toolchain.arm56_so`). Warns, rather than fails,
if the loaded extension does not declare `arm56_version()`.

**Output:** one `<sanitized_path>.json` per target, plus `_batch_report.json`.

**Example:**
```bash
./bin/ioncube-strip symbols --files files.list --output /tmp/symbols
```

## dump — Legacy Literal-Pool Dump

> Needs the **legacy** arm56 build. The extension in this repository writes
> JSON, and this command will collect nothing against it — it refuses to start
> when it detects v4 rather than reporting an empty success. See
> `docs/CONFIGURATION.md`, "Two arm56 generations".

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
2. For each file: executes under PHP 5.6 + legacy arm56
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

> Consumes the legacy hex-dump format. If you have no legacy build, this stage
> has no input.

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

Note that deduplication is by whole *run*, not by word: `ascii_runs` returns
maximal runs, so `"dup dup dup"` is one 15-byte string, not three.

**Example:**
```bash
# Extract pools
./bin/ioncube-strip pool --dumps /tmp/workdir/dumps --output /tmp/workdir

# View results
cat /tmp/workdir/pools/myFunction.txt
cat /tmp/workdir/pools/_index.json | jq .
```

## run — Legacy Pool Pipeline

> The `run` pipeline is the legacy pool path (scan → dump → pool) and therefore
> has the same [legacy arm56 requirement](#dump--legacy-literal-pool-dump) as
> `dump`. It is **not** part of the `manifest`/`symbols` path; run those
> separately.

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

## Working with Large Codebases

`manifest` and `symbols` take a file list, so batch by splitting the list and
running each batch into the same output directory. Already-processed files are
skipped on the second pass.

```bash
./bin/ioncube-strip scan --source /big/codebase --output all_files.list

split -l 100 all_files.list batch_
for batch in batch_*; do
  ./bin/ioncube-strip manifest --files "$batch" --output /tmp/manifests --jobs 4
done
```

## Output Interpretation

### Manifests (`<sanitized_path>.manifest.json`)

Per class: `kind` (class/interface/trait), `abstract`, `final`, `parent`,
`interfaces`, `constants`, and the *own* members only — `own_methods` and
`own_properties` filter out everything inherited, so a marker class does not
appear to declare `Exception`'s methods.

Per method: name, visibility, `static`, `abstract`, and per parameter: name,
`optional`, `default`, `by_ref`, `hint`. A type hint naming an unloadable class
yields `hint: null` rather than aborting the file.

A `hint` of `null` is not evidence the parameter is untyped. It means asking
Reflection for the class threw, which the driver catches per parameter.

### Reports (`_manifest_report.json`, `_batch_report.json`)

Per target: `state` — `ok`, `missing` (blocked on an unresolvable symbol),
`redeclare` (the file declares a symbol that was stubbed), `nodump`, or
`pending`. Plus `stub_symbols` and `skipped_stubs`, the learned and
per-file-waived stubs.

Treat a `redeclare` entry as a signal: it means the file itself declares a
symbol the resolver had stubbed, so the stub set is one step behind the real
class graph. More `redeclare` entries than expected usually means the batch was
too small for the stub resolver to see the declaring file.

### Symbol dumps (`<sanitized_path>.json`)

`stage` is `symbols` on success and may be `compile` for a file that compiled
but yielded no symbols. Each symbol carries `kind`, `name`, `num_literals` and,
for plain PHP, opcodes. For encoded files you get counts and signatures, not
literal content — see `docs/CONFIGURATION.md`, "Neither recovers method
bodies".

### Pool files (`pools/<func>.txt`)

> Legacy path only. Present here for completeness.

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