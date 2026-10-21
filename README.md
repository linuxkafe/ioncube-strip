# ionCube 5.x Decoder

A tool to decode ionCube 5.x-encoded PHP files using Frida-based runtime capture and opcode decoding.

## Quick Start (Recommended)

```bash
# Decode known functions using original working captures (WORKS reliably)
./ioncube-decode /path/to/ioncube/files /tmp/decoded --test-only

# List all ionCube-encoded files in a directory (WORKS)
./ioncube-decode /path/to/php/files /tmp/output --list-only
```

## What Works vs What Doesn't

| Mode | Status | Description |
|------|--------|-------------|
| `--test-only` | ✅ **WORKS** | Decodes `_hash` and `include_compat_libraries` using pre-captured data from base `0x772a62400000` |
| `--list-only` | ✅ **WORKS** | Lists all ionCube-encoded files in a directory |
| (no flags) | ⚠️ **EXPERIMENTAL** | Full pipeline requires Frida keybuf capture for new ASLR sessions — keybuf capture not working reliably |

**Bottom line:** Use `--test-only` for reliable results. The full pipeline is a research prototype.

## Prerequisites

### For `--test-only` (recommended):
- Nothing! Uses pre-captured data from the repo.

### For full pipeline (experimental):
- Docker container named `ioncube-php56` with:
  - PHP 5.6 + ionCube Loader 5.x
  - Frida installed at `/usr/local/bin/frida`
- Target PHP files accessible at `/work/<project>` inside container

## Installation

```bash
# Make executable
chmod +x ioncube-decode

# (Only needed for full pipeline - not for --test-only)
docker cp lib/keybuf_capture_production_v3.js ioncube-php56:/tmp/
```

## Usage

### Decode Known Functions (WORKS)
```bash
./ioncube-decode /path/to/ioncube/files /tmp/decoded --test-only
```

This uses original working captures (base `0x772a62400000`) with verified keybufs.
Output:
```
/tmp/decoded/
├── decoded_hash.php/
│   └── frida_capture_hash_1_pseudo.php    # Opcode listing for _hash
└── decoded_include.php/
    └── frida_capture_include_compat_pseudo.php  # Opcode listing for include_compat
```

### List Encoded Files (WORKS)
```bash
./ioncube-decode /path/to/php/files /tmp/output --list-only
```

Detects ionCube files by:
- `ionCube` / `ioncube` / `_il_exec` string markers
- Header form: `<?php //xxxxx` (5 hex digits)

### Full Pipeline (EXPERIMENTAL)
```bash
./ioncube-decode /path/to/encoded/php /tmp/output
```

⚠️ **This currently fails** because keybuf capture for new ASLR sessions doesn't work reliably. The script will auto-start the container and copy the Frida script, but the keybuf capture fails.

**Technical details:** The keybuf pointer chain (`loader+0x37ec68 → struct_ptr+0xd0[keyidx]`) only populates for `keyidx=0` in new ASLR sessions. Keybufs for `_hash` (keyidx=31) and `include_compat_libraries` (keyidx=63) are not accessible via the standard pointer chain in new ASLR sessions. This is a known limitation requiring deeper Frida/VM analysis.

## Configuration

The tool can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `IONCUBE_CONTAINER` | `ioncube-php56` | Docker container name |
| `IONCUBE_PHP_PATH` | `/usr/bin/php5.6` | PHP binary in container |
| `IONCUBE_FRIDA_PATH` | `/usr/local/bin/frida` | Frida binary in container |
| `IONCUBE_INI_PATH` | `/tmp/arm56.ini` | PHP ini in container |
| `IONCUBE_WORK_BASE` | `/work` | Base path for PHP files in container |
| `IONCUBE_PROJECT` | `whmcs` | Project name under work base |

Example:
```bash
IONCUBE_CONTAINER=my-php56 ./ioncube-decode /work/project /tmp/out --test-only
```

## Architecture

```
ioncube-decode (Python wrapper)
    │
    ├── Scans for ionCube files
    ├── Extracts entry points (_hash, include_compat_libraries)
    ├── Generates Frida test script
    ├── Runs Frida capture (keybuf_capture_production_v3.js)
    │   ├── Hooks VM loop (loader+0x87205) → OPARRAY
    │   └── Keybuf capture: EXPERIMENTAL
    │
    ├── Decodes (lib/full_decoder.py)
    │   ├── handler = raw ^ sign_extend64(keybuf[i] * 0x01010101)
    │   └── operand_type = raw_operand_type ^ keybuf[i]
    │
    └── Outputs opcode listings (pseudo-PHP)
```

## Decoding Formula

```
handler = raw_handler ^ sign_extend64(keybuf[i] * 0x01010101)
operand_type = raw_operand_type ^ keybuf[i]
```

## Current Status

| Function | Keyidx | Oplines | Handlers Matched |
|----------|--------|---------|------------------|
| `_hash` | 31 | 52 | 38/52 (73%) |
| `include_compat_libraries` | 63 | 85 | 66/85 (78%) |

The original captures at base `0x772a62400000` work perfectly.

## Output Format

The tool produces **opcode listings** (pseudo-PHP) for analysis, NOT executable PHP:

```php
<?php
// Decoded from: /work/project/includes/functions.php
// Function: functions
// Oplines: 52
// Keyidx: 31

    0: UNKNOWN_0x772a6248b08a         OP1(0x772a50d83050) OP2(0x655100000000) RES(0xffffffe0) [TYPE_17/TYPE_82] ext=268435456
    1: UNKNOWN_0x772a624d54d0         OP1(0x1)        OP2(0x0)        RES(0xffffffe0) [UNUSED/TYPE_12]
    ...
```

Unknown handlers (`UNKNOWN_`) indicate handlers not in the handler map — these can be reverse engineered.

## Files

```
ioncube-strip/
├── ioncube-decode                     # Main entry point (simple, 327 lines)
├── ioncube-decoder                    # Legacy wrapper (kept for reference)
├── lib/
│   ├── keybuf_capture_production_v3.js  # Frida capture script (EXPERIMENTAL)
│   ├── full_decoder.py                   # Complete decoder pipeline
│   ├── handler_map.txt                   # Handler ID → name mapping
│   └── opcode_decoder.py                 # Core decoding logic
├── captures/
│   ├── frida_capture_hash_1.json         # Original _hash OPARRAY (base 0x772a62400000)
│   ├── frida_capture_include_compat.json # Original include_compat OPARRAY
│   ├── keybuf_31.json                    # Original keybuf for keyidx=31
│   └── keybuf_63.json                    # Original keybuf for keyidx=63
└── README.md
```

## Development

To fix keybuf capture for new ASLR sessions:
- The keybuf pointer chain (`loader+0x37ec68 → struct_ptr+0xd0[keyidx]`) only works for `keyidx=0` in new ASLR sessions
- Keybufs for `_hash` (keyidx=31) and `include_compat_libraries` (keyidx=63) are not accessible via the standard pointer chain
- Possible approaches:
  - Hook keybuf LOAD at `loader+0x872C1` (instruction: `mov rax, qword ptr [rdx + rax*8]`) — crashes with Interceptor
  - Hook keybuf READ at `loader+0x87381` (instruction: `mov ecx, dword ptr [rcx + rsi*4]`) — crashes with Interceptor
  - Use Frida Stalker to trace keybuf load without Interceptor
  - Find alternative keybuf storage location in VM context
- The working captures are from base `0x772a62400000` — only that ASLR session has all keybufs accessible

## License

Internal tool for ionCube 5.x decoding research.