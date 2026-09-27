# ioncube-strip — Measured validation on WHMCS 5.3.12

Evidence, not claims. Everything below was run on this machine; the commands
are reproducible and the environment is named so the numbers can be re-checked
or falsified.

## Verdict

**Usable, with a sharp boundary.** `manifest` and `symbols` recover class shape
from WHMCS at 100% on class-bearing files, in about a second, and two
independent mechanisms agree exactly. The literal-pool premise is not usable
and, on the evidence below, is not usable *in principle* with this toolchain.

Do not discard the project. Discard the `dump`/`pool` half of its stated
purpose.

## Environment

| Component | Value |
|---|---|
| PHP | 5.6.40 (`/usr/bin/php5.6`, sury build, API 20131106) |
| ionCube Loader | `ioncube_loader_lin_5.6.so`, reports "the ionCube PHP Loader + ionCube24" |
| arm56 | in-tree v4, `arm56_version()` → `4.0.0-spike` |
| Corpus | WHMCS 5.3.12 (build 1ccd2bb.50, 24 Feb 2015), `/home/seyon/dev/whmcs` |
| Encrypted files found by the scanner | 516 |

The Loader must be the first `zend_extension`, so the run uses a dedicated ini
with `PHP_INI_SCAN_DIR=''` — the stock Debian ini loads opcache as a
`zend_extension` at priority 10 and conflicts.

## Results

### Class-bearing files: total success

`includes/classes`, 90 encrypted files:

| Metric | `manifest` | `symbols` |
|---|---|---|
| Files resolved | 90 / 90 (100%) | 90 / 90 (100%) |
| Classes | 88 | — |
| **Methods** | **1028** | **1028** |
| Mismatches | — | **0** |
| Properties | 260 | — |
| Constants | 32 | — |
| Wall clock | 0.95 s (4 jobs) | 1.01 s (4 jobs) |

The method counts agreeing to the unit across 90 files, from mechanisms that
share nothing but the file list, is the single strongest result here.

The stub resolver converged in 3 rounds, learning 20 missing symbols
(`LogicExceptions`, `PHPMailer`, `Smarty`, `Smarty_Compiler`, `TCPDF`, …) and
waiving stubs for 3 files that declare a symbol it had stubbed.

Recovered shape is directly usable. For example `WHMCS_License` resolves to 60
methods / 13 properties including `getLicenseKey`, `getHosts`, `getCArray`,
`getVersion`, `getHash`, and `WHMCS_TokenManager` to 19 methods including
`conditionallySetToken` and `generateToken`.

### Doc comments survive encryption

arm56's JSON carries `doc_comment`, which the encoder does not encrypt:

| | Count | Share |
|---|---|---|
| Symbols with a doc comment | 335 | 32.6% |
| With any `@tag` | 327 | 31.8% |
| With `@param` | 192 | — |
| With `@return` | 288 | — |
| Distinct `@param` types recovered | 24 | — |

Recovered types include `WHMCS_Config_AbstractConfig`, `WHMCS_Database`,
`WHMCS_Init`, `WHMCS_Terminus`, `WHMCS_Version_SemanticVersion`,
`WHMCS_Payment_Filter_FilterInterface`, plus unions such as `array|string` and
`bool|int`. For reconstruction this is domain knowledge the source would have
carried, not something inferable from method names.

### Method bodies are genuinely not recoverable

arm56's own output settles this, rather than leaving it to inference:

- `content_faulted: true` on methods whose literal bucket could not be walked
- `num_ops: 0` — the opcode stream is empty for every encoded method
- `num_literals` is a **count** (`33853` across the run), never content

So `op_array->reserved[3]` being NULL and the Loader freeing the pool is not a
limitation of this implementation. There is nothing to extract. **T017 is
settled against the pool path.** The `dump`/`pool` code is retained, tested and
clearly labelled legacy; it should not be advertised as a capability.

### Where it does not work, and why

Across the full 516-file corpus, 167 files (32%) yield class shape. The 349 that
do not break down as:

| Count | Cause | Recoverable? |
|---|---|---|
| 173 | Process emits nothing — the file calls `exit`/`die` at include time | No. Sampled 40: **0 declared any class.** Nothing to recover |
| 94 | `require '../init.php'` — needs the live application (config, DB) | No, not without a running WHMCS |
| 60 | Needs globals (`$whmcs`) or an undefined method | No, same reason |
| 15 | Parse error under PHP 5.6 | Investigate individually |
| 7 | Other fatals (`ROOTDIR` constant, missing function) | Investigate individually |

The distinction that matters: the 173 are not a failure. They are procedural
route files that terminate the process and declare no classes, so there is no
class shape to recover. The 94 + 60 are admin/API entry points that cannot load
without a database. **Neither category is a class-definition file**, which is
what this method can read.

## Reproducing

```bash
export IONCUBE_STRIP_PHP56=/usr/bin/php5.6
export IONCUBE_STRIP_INI=/path/to/ini-with-loader-first
export IONCUBE_STRIP_ARM56=/path/to/arm56/modules/arm56.so
export IONCUBE_STRIP_CORPUS=/path/to/whmcs/includes/classes

python3 -m pytest tests/ -q          # 76 passed, 0 skipped

# or drive it directly
./bin/ioncube-strip scan --source "$IONCUBE_STRIP_CORPUS" --output files.list
./bin/ioncube-strip manifest --files files.list --output manifests --jobs 4
./bin/ioncube-strip symbols  --files files.list --output symbols  --jobs 4
```

Pointing `IONCUBE_STRIP_CORPUS` at a class directory maximises yield. A whole
application tree is dominated by bootstrap-dependent route files.

## What this validation found and fixed

The toolchain had been present the whole time. An earlier pass concluded
"no PHP 5.6 in this environment" from the absence of `/usr/local/bin/php5.6`
without searching, and shipped a suite whose toolchain tier had never run.
Running it for the first time exposed four defects that no unit test could
have, because every unit test used a fake `php`:

1. **`probe_arm56.py` loaded arm56 with `zend_extension=`.** arm56 declares a
   plain `zend_module_entry` (`arm56.c:950`). Loading it the wrong way reports
   *"doesn't appear to be a valid Zend extension"* and the probe then answered
   `unverified` — a wrong answer rather than an error, on every real system.
2. **Config overrode the environment**, the opposite of the documented
   precedence. `resolve_toolchain` assigned the config values over already
   exported variables, so `PHP56=/usr/bin/php5.6` was silently ignored in
   favour of the example config's `/usr/local/bin/php5.6`. The CLI was
   unusable on any machine whose paths differ from the example.
3. **`PHP56_EXTRA` unbound** under `set -u` when neither environment nor config
   mentioned it.
4. **The toolchain tests used the same wrong load method**, and set
   `IONCUBE_STRIP_*` variables that the tools never read, so even a corrected
   load would have found no toolchain.

Defect 2 is the one that mattered most: the tool was unusable on this machine
and no test could have said so, because the tests exercised the Python
precedence (correct) and never the bash.

## Honest limits of this validation

- One corpus, one ionCube Loader generation (`ionCube24`), one PHP patchlevel.
  Nothing here says anything about other ionCube versions or loaders.
- The 15 parse errors and 7 other fatals were counted, not diagnosed.
- `symbols` emits a JSON file for the resolver's own generated `driver.php`,
  because arm56 dumps every compiled file. Harmless — 122 of 212 files, and
  all 90 targets parse — but it pollutes the output directory.
- The doc-comment figure counts comments present, not their usefulness.
