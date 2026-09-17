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