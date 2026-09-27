# ioncube-strip — Configuration Reference

## Configuration File

Default location: `ioncube-strip.yaml` in current directory, or `~/.config/ioncube-strip/config.yaml`

Command-line option: `--config /path/to/config.yaml`

## Full Schema

```yaml
toolchain:
  php56: "/usr/local/bin/php5.6"
  php56_ini: "/etc/php56/php.ini"
  arm56_so: "/usr/local/lib/arm56.so"
  arm56_tmp: "/tmp/arm56_output"

markers:
  - pattern: "_il_exec"
    type: "substring"
  - pattern: "^//\\s*00e5"
    type: "regex"

output:
  dumps_dir: "dumps"
  pools_dir: "pools"
  index_file: "_index.json"

extraction:
  min_run_length: 3
  max_run_length: 2000
  charset: "ascii"
  workers: 0

parallelism:
  dump_jobs: 1
  pool_workers: 0
```

## Section Reference

### toolchain (required for dump)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `php56` | string | `/usr/local/bin/php5.6` | PHP 5.6 CLI binary path |
| `php56_ini` | string | `/etc/php56/php.ini` | PHP 5.6 ini file path |
| `arm56_so` | string | `/usr/local/lib/arm56.so` | arm56 extension path |
| `arm56_tmp` | string | `/tmp/arm56_output` | arm56 output directory |

**Environment overrides:** `PHP56`, `PHP56_INI`, `ARM56_SO`, `ARM56_TMP`

### markers

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pattern` | string | — | Marker pattern |
| `type` | string | `"substring"` | `"substring"` or `"regex"` |

**Default markers:**
```yaml
markers:
  - pattern: "_il_exec"
    type: "substring"
  - pattern: "^//\\s*00e5"
    type: "regex"
```

**Adding custom markers:**
```yaml
markers:
  - pattern: "_il_exec"
    type: "substring"
  - pattern: "^//\\s*00e5"
    type: "regex"
  - pattern: "ionCube Loader"
    type: "substring"
```

### output

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `dumps_dir` | string | `"dumps"` | Dumps directory (relative to output root) |
| `pools_dir` | string | `"pools"` | Pools directory (relative to output root) |
| `index_file` | string | `"_index.json"` | Index filename (inside pools_dir) |

### extraction

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `min_run_length` | integer | `3` | Minimum ASCII run length |
| `max_run_length` | integer | `2000` | Maximum ASCII run length |
| `charset` | string | `"ascii"` | `"ascii"` or `"utf-8"` |
| `workers` | integer | `0` | Worker processes (0 = CPU count) |

**Tuning tips:**
- Increase `min_run_length` to reduce noise (try 4-5)
- Decrease `max_run_length` if seeing binary garbage
- `charset: "utf-8"` is experimental — may produce mojibake

### parallelism

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `dump_jobs` | integer | `1` | Parallel dump jobs |
| `pool_workers` | integer | `0` | Pool extraction workers (0 = CPU count) |

**⚠️ Warning:** `dump_jobs > 1` uses shared `ARM56_TMP` directory. Only safe if you configure unique temp dirs per job (not currently supported). Keep at 1.

## Environment Variables

All toolchain settings can be overridden via environment:

```bash
export PHP56=/opt/php56/bin/php
export PHP56_INI=/opt/php56/php.ini
export ARM56_SO=/opt/php56/arm56.so
export ARM56_TMP=/var/tmp/arm56
```

## Example Configurations

### Minimal (all defaults)

```yaml
# ioncube-strip.yaml
# Uses all defaults, just need to set toolchain paths via env
```

### Custom Paths

```yaml
toolchain:
  php56: "/home/user/php56/bin/php"
  php56_ini: "/home/user/php56/php.ini"
  arm56_so: "/home/user/arm56/modules/arm56.so"
  arm56_tmp: "/home/user/arm56_output"
```

### Aggressive Extraction

```yaml
extraction:
  min_run_length: 4
  max_run_length: 1000
  charset: "ascii"
  workers: 8
```

### Custom Markers (for non-WHMCS ionCube)

```yaml
markers:
  - pattern: "_il_exec"
    type: "substring"
  - pattern: "^//\\s*00e5"
    type: "regex"
  - pattern: "ionCube"
    type: "substring"
```

## Validation

Validate your config:

```bash
python3 -c "
import yaml, sys
with open('ioncube-strip.yaml') as f:
    cfg = yaml.safe_load(f)
required = ['toolchain', 'markers', 'output', 'extraction', 'parallelism']
for r in required:
    assert r in cfg, f'Missing: {r}'
print('Config valid')
"
```

Or use the Makefile target:

```bash
make validate-config
```

## Two arm56 generations

This repository contains two arm56 extensions' worth of expectations, and they
are **not interchangeable**. Read this before trusting any stage.

| | v4 (in this repo) | legacy (not in this repo) |
|---|---|---|
| Source | `arm56/arm56.c`, self-described "arm56 v4 (E1 spike)" | the original extension; must be obtained separately |
| Hook | wraps `zend_compile_file` (`arm56.c:54,784`) | function entry, `op_array->reserved[3]` |
| Output | JSON, `<ARM56_JSON>/<sanitized>.json` (`arm56.c:722`) | hex dumps, `<ARM56_TMP>/_path.php.fn.func_0x1.txt` |
| Enabled by | `ARM56_JSON` set | `ARM56_TMP` |
| Drives | `symbols`, `manifest` | `dump`, `pool` |
| Recovers | class shape, method signatures, literal *counts* | literal pool strings |

`grep -c hex arm56/arm56.c` returns 0: the in-tree extension has no hex writer
at all. So **`ioncube-strip dump` and `ioncube-strip pool` cannot work with the
extension in this repository.** They need the legacy build.

They also fail *quietly*, which is the reason for the probe below.
`collect_dumps.py:38` globs `ARM56_TMP` for the legacy pattern, finds nothing,
returns `False`, and the pipeline reports "no dumps collected" — the same
output as a genuinely empty result. The `dump` subcommand therefore refuses to
start when it detects a v4 extension loaded, rather than reporting a
successful run that produced nothing.

### Identifying the loaded extension

```bash
python3 lib/probe_arm56.py --config config/ioncube-strip.yaml.example
python3 lib/probe_arm56.py --expect v4    # exit 3 on mismatch
```

The probe calls `arm56_version()` (`arm56.c:820`), which the v4 extension uses
to declare itself. Its **presence** identifies v4. Its **absence** is reported
as `unverified`, never as `legacy`: an unrelated or older extension produces the
same signal, and treating that as proof would be a guess.

## Extraction tools

Two commands read encrypted files under PHP 5.6 with the ionCube Loader. Both
take the same arguments and both write a report describing every file. Both
work with the in-tree v4 extension.

```bash
ioncube-strip manifest --files list.txt --source /path/to/tree --output /path/to/out
ioncube-strip symbols  --files list.txt --source /path/to/tree --output /path/to/out

# equivalently
make manifest FILES=list.txt SOURCE=/path/to/tree OUTPUT=/path/to/out CONFIG=cfg.yaml
make symbols  FILES=list.txt SOURCE=/path/to/tree OUTPUT=/path/to/out CONFIG=cfg.yaml
```

`FILES` is a newline-separated list of paths, absolute or relative to `SOURCE`.

### `class_manifest.py` — Reflection manifests

Preferred evidence for reconstructing a class. While a file is still encrypted
the Loader must resolve its inheritance to load it, so Reflection reports the
true parent, interfaces, constants, properties and method signatures. Needs
`json_encode` in the 5.6 build; if `php56_ini` does not provide it, set
`toolchain.php56_extra` (or `PHP56_EXTRA`) to the extension path. Does not need
arm56 at all.

### `dump_batch.py` — arm56 symbol dumps

Yields per-method literal counts and opcodes for plain PHP, and literal counts
plus signatures for encoded files. Needs the v4 extension (`toolchain.arm56_so`)
for `arm56_dump()`.

### Neither recovers method bodies

Literal string content is not obtainable: the Loader frees the pool once a body
has run, `zend_execute_ex` is not re-entered for encoded code, and
`op_array->reserved[3]` is NULL. Bodies require executing the code with the
original toolchain present, or reconstructing from signatures and domain
knowledge.

Note what this implies for the legacy path: if the pool is unrecoverable in
principle, then `dump` and `pool` are not merely unavailable for want of the
legacy build — they may have no output to produce. That question is open, and
is tracked as such in `docs/ROADMAP.md`.

### Cross-check

On the WHMCS `includes/classes` block both tools reported **1028 methods across
104 files** on one machine, from independent mechanisms.

That figure is an observation, not an invariant: it is a property of that
corpus, not of the tools, and a different corpus will legitimately yield a
different number. The claim worth asserting — and the one
`tests/integration/test_extraction.py::test_manifest_and_symbols_agree_on_the_method_count`
asserts — is that the two mechanisms *agree* on whatever corpus is supplied.
A disagreement means one of the two is wrong; treat it as a defect signal
rather than noise.
