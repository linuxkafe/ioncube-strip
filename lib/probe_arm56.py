#!/usr/bin/env python3
"""
probe_arm56.py — classify the arm56 extension that is actually loaded.

The repository carries two incompatible arm56 generations, and they are not
interchangeable:

- **v4** (vendored at arm56/arm56.c) hooks zend_compile_file and writes JSON
  named by ARM56_JSON. Drives `symbols` and `manifest`.
- **legacy** (the original extension, not in this repository) hooks function
  entry and writes hex dumps named ARM56_TMP, as
  `_path.php.fn.func_0x1.txt`. Drives `dump` and `pool`.

Running a stage against the wrong one does not fail loudly. `collect_dumps.py`
globs for a pattern that never appears, returns False, and the pipeline reports
"no dumps collected" — indistinguishable from a genuinely empty result. The
probe exists to turn that silence into an error.

arm56_version() (arm56.c:820) is the v4 extension declaring itself, so its
presence is a positive identification. Its absence is NOT proof of legacy: an
unrelated or older extension would look the same. That case is reported as
`unverified` and never silently treated as legacy.

Usage:
    python3 probe_arm56.py --config CONFIG
    python3 probe_arm56.py --config CONFIG --expect v4

Exit codes:
    0  the loaded extension matches --expect (or --expect was not given)
    3  the loaded extension does not match --expect
    4  the extension could not be loaded or interrogated at all

SPDX-License-Identifier: MIT
"""
import argparse
import json
import os
import subprocess
import sys

# Emitted by the v4 extension's arm56_version(). arm56.c:35.
V4_MARKER = '4.0.0-spike'

PROBE_PHP = (
    'echo function_exists("arm56_version") ? '
    '"arm56_version()=" . arm56_version() : '
    '"arm56_version() absent";'
)


def probe(php, ini, arm56_so, timeout=15):
    """Return the generation classification for the loaded extension."""
    cmd = [php, '-c', ini, '-d', f'zend_extension={arm56_so}', '-r', PROBE_PHP]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'generation': 'unloadable', 'detail': str(exc)}

    out = proc.stdout.decode('utf-8', 'replace').strip()
    err = proc.stderr.decode('utf-8', 'replace').strip()

    if proc.returncode != 0:
        return {'generation': 'unloadable', 'detail': err or out,
                'returncode': proc.returncode}

    if out.startswith('arm56_version()='):
        version = out.split('=', 1)[1]
        return {'generation': 'v4' if V4_MARKER in version else 'unknown',
                'version': version}

    if 'absent' in out:
        # Not proof of the legacy extension: only of the absence of v4.
        return {'generation': 'unverified', 'detail': out}

    return {'generation': 'unloadable', 'detail': out or 'no probe output'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', help='ioncube-strip.yaml with the toolchain paths')
    ap.add_argument('--expect', choices=('v4', 'legacy'),
                    help='fail unless the loaded extension is this generation')
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    args = ap.parse_args()

    from dump_batch import resolve_toolchain

    php, ini, arm56, _extra = resolve_toolchain(args.config)
    for label, value in (('PHP56', php), ('PHP56_INI', ini), ('ARM56_SO', arm56)):
        if not value or not os.path.exists(value):
            result = {'generation': 'unconfigured', 'detail': f'{label} not found: {value}'}
            _emit(result, args, expect=args.expect)
            return 4

    result = probe(php, ini, arm56)
    _emit(result, args, expect=args.expect)
    return 0


def _emit(result, args, expect):
    if args.json:
        print(json.dumps(result, indent=1))
    elif result['generation'] == 'v4':
        print(f"arm56 generation: v4 ({result.get('version', '?')})")
    elif result['generation'] == 'unverified':
        print('arm56 generation: unverified — arm56_version() is absent, so this '
              'is not the in-tree v4 extension. It may be the legacy hex-dump '
              'build, or something else entirely.')
    else:
        print(f"arm56 generation: {result['generation']} — "
              f"{result.get('detail', '')}")

    if expect is None:
        return
    if result['generation'] == expect:
        return
    if expect == 'legacy' and result['generation'] == 'unverified':
        # Reported as unverified on purpose: absence of arm56_version() is not
        # evidence that the legacy build is present.
        print('ERROR: expected the legacy arm56 build, but the loaded '
              'extension is unverified. See docs/CONFIGURATION.md.',
              file=sys.stderr)
        raise SystemExit(3)
    print(f'ERROR: expected arm56 generation {expect}, found '
          f'{result["generation"]}. See docs/CONFIGURATION.md '
          f'("Two arm56 generations").', file=sys.stderr)
    raise SystemExit(3)


if __name__ == '__main__':
    sys.exit(main())
