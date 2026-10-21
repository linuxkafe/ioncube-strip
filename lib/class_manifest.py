#!/usr/bin/env python3
"""
class_manifest.py — Reflection manifests for ionCube-encrypted PHP classes.

While an encrypted file is still encrypted, the Loader must resolve its
inheritance in order to load it. Reflection therefore reports the *true* parent,
interfaces, constants, properties and method signatures. That makes this the
primary evidence for reconstructing a class declaration, ahead of the arm56
symbol dump — signatures confirm it, Reflection is what you cannot invent.

This matters in practice: in the WHMCS 5.3 exception tree, three of fourteen
classes did not extend the base class an assumption would have picked.

Bodies are not recoverable this way. The manifest gives shape, not behaviour.

Usage:
    python3 class_manifest.py --files LIST --output DIR [--source DIR]
                             [--config CONFIG] [--limit N] [--jobs N]

Writes one JSON document per target file plus _manifest_report.json.

SPDX-License-Identifier: MIT
"""
import argparse
import json
import os
import sys

from stub_resolver import STUB_PREAMBLE, StubResolver, sanitize

# The driver reports the manifest as JSON on stdout. json_encode must exist in
# the 5.6 build, which is not guaranteed by a minimal php.ini, so the extension
# is requested explicitly and its absence is reported rather than guessed at.
DRIVER_BODY = STUB_PREAMBLE + """
if (!function_exists('json_encode')) {
    fwrite(STDERR, "ERROR: json_encode unavailable; the toolchain php.ini must "
        . "load the json extension\\n");
    exit(3);
}

/* No error suppression: the Loader reports unresolved references as a fatal,
 * and hiding it would hide the symbol name we need to stub. */
include $target;

$out = array('file' => $target, 'classes' => array());

foreach (array_merge(get_declared_classes(), get_declared_interfaces()) as $c) {
    $r = new ReflectionClass($c);
    if ($r->getFileName() !== $target) { continue; }

    $entry = array(
        'name'       => $c,
        'kind'       => $r->isInterface() ? 'interface'
                      : ($r->isTrait() ? 'trait' : 'class'),
        'abstract'   => $r->isAbstract(),
        'final'      => $r->isFinal(),
        'parent'     => $r->getParentClass() ? $r->getParentClass()->getName() : null,
        'interfaces' => array_values($r->getInterfaceNames()),
        'constants'  => $r->getConstants(),
        'own_methods'    => 0,
        'own_properties' => 0,
        'methods'    => array(),
        'properties' => array(),
    );

    foreach ($r->getMethods() as $m) {
        if ($m->getDeclaringClass()->getName() !== $c) { continue; }
        $entry['own_methods']++;
        $params = array();
        foreach ($m->getParameters() as $p) {
            $hint = null;
            try { $hint = $p->getClass() ? $p->getClass()->getName() : null; }
            catch (ReflectionException $e) { $hint = null; }
            $params[] = array(
                'name'     => $p->getName(),
                'optional' => $p->isOptional(),
                'default'  => $p->isDefaultValueAvailable() ? $p->getDefaultValue() : null,
                'by_ref'   => $p->isPassedByReference(),
                // A type hint may name a class that is not loadable; asking
                // Reflection for it throws rather than returning null.
                'hint'     => $hint,
            );
        }
        $entry['methods'][] = array(
            'name'       => $m->getName(),
            'visibility' => $m->isPrivate() ? 'private'
                          : ($m->isProtected() ? 'protected' : 'public'),
            'static'     => $m->isStatic(),
            'abstract'   => $m->isAbstract(),
            'params'     => $params,
        );
    }

    foreach ($r->getProperties() as $p) {
        if ($p->getDeclaringClass()->getName() !== $c) { continue; }
        $entry['own_properties']++;
        $entry['properties'][] = array(
            'name'       => $p->getName(),
            'visibility' => $p->isPrivate() ? 'private'
                          : ($p->isProtected() ? 'protected' : 'public'),
            'static'     => $p->isStatic(),
        );
    }

    $out['classes'][] = $entry;
}

echo json_encode($out), "\\n";
"""


def manifest_path(outdir, target):
    return os.path.join(outdir, sanitize(target) + '.manifest.json')


def read_manifest(outdir, target):
    """Returns the parsed manifest, or None if absent or unreadable."""
    path = manifest_path(outdir, target)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            doc = json.load(fh)
    except (ValueError, OSError):
        return None
    if not isinstance(doc, dict) or 'classes' not in doc:
        return None
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--files', required=True, help='newline-separated target list')
    ap.add_argument('--source', help='base directory for relative paths')
    ap.add_argument('--output', required=True, help='directory for manifests')
    ap.add_argument('--config', help='ioncube-strip.yaml with the toolchain paths')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--rounds', type=int, default=8)
    ap.add_argument('--timeout', type=int, default=30)
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    from dump_batch import resolve_toolchain

    php, ini, _arm56, extra = resolve_toolchain(args.config)
    if not php or not os.path.exists(php):
        sys.exit(f'ERROR: PHP56 not found: {php}')
    if not ini or not os.path.exists(ini):
        sys.exit(f'ERROR: PHP56_INI not found: {ini}')

    # The manifest driver reports through json_encode, which a minimal 5.6
    # php.ini may not provide; arm56 is not needed for Reflection.
    extensions = [e for e in extra if e]

    with open(args.files, encoding='utf-8') as fh:
        targets = [l.strip() for l in fh if l.strip()]
    if args.source:
        targets = [t if os.path.isabs(t) else os.path.join(args.source, t)
                   for t in targets]
    if args.limit:
        targets = targets[:args.limit]

    os.makedirs(args.output, exist_ok=True)

    resolver = StubResolver(php, ini, extensions, args.output,
                            timeout=args.timeout, jobs=args.jobs,
                            rounds=args.rounds)
    def capture(target, stdout):
        """The driver reports the manifest on stdout; persist it per file."""
        start = stdout.find('{')
        if start < 0:
            return
        try:
            doc = json.loads(stdout[start:])
        except ValueError:
            return
        with open(manifest_path(args.output, target), 'w', encoding='utf-8') as fh:
            json.dump(doc, fh, indent=1)

    resolver.resolve(targets, DRIVER_BODY,
                     lambda t: read_manifest(args.output, t) is not None,
                     capture=capture)

    report = {'files': {}, 'stub_symbols': dict(sorted(resolver.stubs.items())),
              'skipped_stubs': {t: sorted(v) for t, v in resolver.skip.items() if v}}

    for target in targets:
        entry = dict(resolver.status.get(target, {'state': 'pending'}))
        manifest = read_manifest(args.output, target)
        if manifest:
            classes = manifest['classes']
            entry['classes'] = [c['name'] for c in classes]
            entry['methods'] = sum(c['own_methods'] for c in classes)
            entry['properties'] = sum(c['own_properties'] for c in classes)
            entry['constants'] = sum(len(c['constants']) for c in classes)
        report['files'][target] = entry

    with open(os.path.join(args.output, '_manifest_report.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(report, fh, indent=1)

    if not args.quiet:
        resolver.summary(len(targets))
        ok = [v for v in report['files'].values() if v.get('classes')]
        if ok:
            print(f'classes: {sum(len(v["classes"]) for v in ok)} | '
                  f'methods: {sum(v["methods"] for v in ok)} | '
                  f'properties: {sum(v["properties"] for v in ok)} | '
                  f'constants: {sum(v["constants"] for v in ok)}')


if __name__ == '__main__':
    main()
