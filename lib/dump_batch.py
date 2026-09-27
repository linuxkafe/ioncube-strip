#!/usr/bin/env python3
"""
dump_batch.py — batch symbol extraction for ionCube-encrypted PHP files.

Runs one PHP 5.6 process per target file under the ionCube Loader, with
arm56 loaded, and records the symbols the loader registers for it.

Encrypted library files reference each other (interfaces, abstract parents)
that live in other encrypted files. The Loader resolves those references at
include time and raises an ordinary PHP fatal when they are missing, which
kills the process. This runner therefore learns the missing symbol names from
the error output, pre-declares them as stubs, and iterates until the set
stops growing.

Stubs are only ever declared for symbols that no successfully-loaded file has
provided, so a real class is never shadowed. Because a fatal error cannot be
caught, every attempt runs in its own process.

Usage:
    python3 dump_batch.py --files LIST --output DIR [--config CONFIG]
                          [--limit N] [--jobs N]

The file list is a newline-separated list of paths, absolute or relative to
--source. Output is one JSON document per target file plus a _batch_report.json
summarising per-file status.

SPDX-License-Identifier: MIT
"""
import argparse
import json
import os
import sys

from stub_resolver import STUB_PREAMBLE, StubResolver, sanitize

DRIVER_BODY = STUB_PREAMBLE + """
if (!function_exists('arm56_dump')) {
    fwrite(STDERR, "ERROR: arm56_dump() is not available; the arm56 extension "
        . "must be loaded\n");
    exit(3);
}

/* No error suppression: the Loader reports unresolved class references as an
 * ordinary fatal, and suppressing it hides the symbol name we need to stub. */
include $target;

$classes = array();
foreach (get_declared_classes() as $c) {
    $r = new ReflectionClass($c);
    if ($r->getFileName() === $target) { $classes[] = $c; }
}
foreach (get_declared_interfaces() as $i) {
    $r = new ReflectionClass($i);
    if ($r->getFileName() === $target) { $classes[] = $i; }
}

arm56_dump($target, implode(',', $classes));
"""


def symbols_path(outdir, target):
    return os.path.join(outdir, sanitize(target) + '.json')


def read_symbols(outdir, target):
    """Returns the symbols document, or None if absent or unparseable."""
    path = symbols_path(outdir, target)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            doc = json.load(fh)
    except (ValueError, OSError):
        return None
    if not isinstance(doc, dict) or doc.get('stage') != 'symbols':
        return None
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--files', required=True, help='newline-separated list of target files')
    ap.add_argument('--source', help='base directory for relative paths in the list')
    ap.add_argument('--output', required=True, help='directory for JSON output')
    ap.add_argument('--config', help='ioncube-strip.yaml providing the toolchain paths')
    ap.add_argument('--limit', type=int, help='process at most N files')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--rounds', type=int, default=6,
                    help='max dependency-resolution rounds')
    ap.add_argument('--timeout', type=int, default=30)
    args = ap.parse_args()

    php, ini, arm56, extra = resolve_toolchain(args.config)
    for label, value in (('PHP56', php), ('PHP56_INI', ini), ('ARM56_SO', arm56)):
        if not value or not os.path.exists(value):
            sys.exit(f'ERROR: {label} not found: {value}')

    with open(args.files, encoding='utf-8') as fh:
        targets = [l.strip() for l in fh if l.strip()]
    if args.source:
        targets = [t if os.path.isabs(t) else os.path.join(args.source, t) for t in targets]
    if args.limit:
        targets = targets[:args.limit]

    os.makedirs(args.output, exist_ok=True)

    # name -> declaration line, e.g. "WHMCS_Foo" -> "interface WHMCS_Foo {}"
    # arm56 writes its JSON into the directory named by ARM56_JSON, and writes
    # nothing at all when it is unset.
    extensions = [e for e in ([arm56] if arm56 else []) + list(extra)]
    resolver = StubResolver(php, ini, extensions, args.output,
                            env={'ARM56_JSON': args.output},
                            timeout=args.timeout, jobs=args.jobs,
                            rounds=args.rounds)
    status = resolver.resolve(targets, DRIVER_BODY,
                              lambda t: read_symbols(args.output, t) is not None)

    write_report(args.output, targets, status, resolver.stubs, resolver.skip)
    summarise(targets, status)




def write_report(outdir, targets, status, stubs, skip):
    report = {
        'files': {},
        'stub_symbols': dict(sorted(stubs.items())),
        'skipped_stubs': {t: sorted(v) for t, v in skip.items() if v},
    }
    for target in targets:
        entry = dict(status.get(target, {'state': 'pending'}))
        doc = read_symbols(outdir, target)
        if doc:
            syms = doc.get('symbols', [])
            entry['classes'] = doc.get('classes', [])
            entry['symbols'] = len(syms)
            entry['methods'] = sum(1 for s in syms if s.get('kind') == 'method')
            entry['functions'] = sum(1 for s in syms if s.get('kind') == 'function')
            entry['literals'] = sum(s.get('num_literals') or 0 for s in syms)
        else:
            entry['symbols'] = None
        report['files'][target] = entry
    with open(os.path.join(outdir, '_batch_report.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(report, fh, indent=1)


def summarise(targets, status):
    counts = {}
    for state in status.values():
        key = state.get('state', 'pending')
        counts[key] = counts.get(key, 0) + 1
    total = len(targets)
    print(f'\n=== batch summary ({total} files) ===')
    for state, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'  {state:<10} {n:4d}  ({100 * n // total}%)')


def resolve_toolchain(config_path):
    """Resolve the PHP 5.6 toolchain.

    Precedence: environment, then the supplied config, then the bundled example.
    Returns (php, ini, arm56_so, extra_extensions) where extra_extensions is a
    list of additional .so paths the driver may need (a minimal php.ini does
    not necessarily provide json_encode).
    """
    php = os.environ.get('PHP56', '')
    ini = os.environ.get('PHP56_INI', '')
    arm56 = os.environ.get('ARM56_SO', '')
    extra = [e for e in os.environ.get('PHP56_EXTRA', '').split(os.pathsep) if e]

    paths = [config_path] if config_path else []
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths.append(os.path.join(here, 'config', 'ioncube-strip.yaml.example'))

    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            import yaml
        except ImportError:
            break
        with open(path, encoding='utf-8') as fh:
            cfg = yaml.safe_load(fh) or {}
        tc = cfg.get('toolchain', {})
        php = php or tc.get('php56', '')
        ini = ini or tc.get('php56_ini', '')
        arm56 = arm56 or tc.get('arm56_so', '')
        configured = tc.get('php56_extra', '')
        if configured and configured not in extra:
            extra.append(configured)

    return php, ini, arm56, extra



if __name__ == '__main__':
    main()
