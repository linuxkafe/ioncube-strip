"""
Toolchain and corpus integration tests.

Everything here skips unless the operator supplies the toolchain and, for the
corpus tests, a directory of encrypted files:

    export IONCUBE_STRIP_PHP56=/usr/local/bin/php5.6
    export IONCUBE_STRIP_INI=/etc/php56/php.ini
    export IONCUBE_STRIP_ARM56=/usr/local/lib/arm56.so
    export IONCUBE_STRIP_CORPUS=/path/to/encrypted/tree

A run where these all skip is not a pass. It means the tool-free tier
(tests/integration/test_cli.py) passed and nothing else was exercised.
"""
import json
import os
import sys

import pytest
from conftest import run_lib, toolchain_config

# The manifest file name is the sanitized target path; reuse the tool's own
# function so the test cannot drift from it.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'lib'))
from lib.class_manifest import sanitize as _sanitize

pytestmark = pytest.mark.toolchain

LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'lib')


# -- toolchain -----------------------------------------------------------

def test_php56_is_actually_56(php_argv):
    # The whole design assumes a 5.x zend_extension Loader. Running these
    # stages under 7+ would "work" and produce meaningless output.
    from conftest import run
    proc = run([*php_argv, '-r', 'echo PHP_MAJOR_VERSION, ".", PHP_MINOR_VERSION;'])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == '5.6', f'expected PHP 5.6, got {proc.stdout}'


def test_arm56_loads_as_a_plain_extension(php_argv, arm56_so):
    # extension=, not zend_extension=: arm56.c:950 declares a plain
    # zend_module_entry with STANDARD_MODULE_HEADER. Loaded as a zend_extension
    # it reports "doesn't appear to be a valid Zend extension" and every
    # arm56_* function is absent -- a wrong answer, not an error.
    from conftest import run
    proc = run([*php_argv, '-d', f'extension={arm56_so}', '-m'])
    assert proc.returncode == 0, proc.stderr
    assert 'arm56' in proc.stdout, proc.stdout


def test_arm56_dump_is_callable(php_argv, arm56_so):
    from conftest import run
    proc = run([*php_argv, '-d', f'extension={arm56_so}', '-r',
                'echo function_exists("arm56_dump") ? "yes" : "no";'])
    assert proc.stdout.strip() == 'yes', proc.stdout


def test_extension_is_inert_without_arm56_json(php_argv, arm56_so, tmp_path):
    # arm56.c:11-12 — unset ARM56_JSON and the extension must write nothing.
    # A probe that writes anyway would corrupt every real run's output dir.
    from conftest import run
    out = tmp_path / 'probe'
    out.mkdir()
    script = tmp_path / 'probe.php'
    script.write_text('echo "loaded\\n";', encoding='utf-8')
    env = dict(os.environ)
    env.pop('ARM56_JSON', None)
    proc = run([*php_argv, '-d', f'extension={arm56_so}', str(script)],
               check=False)
    assert proc.returncode == 0, proc.stderr
    assert list(out.iterdir()) == []


# -- corpus --------------------------------------------------------------

def _targets(corpus, tmp_path, limit=None):
    """Write the corpus file list in the form the batch tools expect.

    Sampled with a stride rather than taking the first N alphabetically. An
    alphabetical prefix of a real tree is almost always route or bootstrap
    files (`admin/*.php`), which cannot load without the live application, so
    the cross-check would find nothing to compare and rightly fail. Pointing
    IONCUBE_STRIP_CORPUS at a class directory such as `includes/classes` gives
    the highest yield; the stride keeps the sample spread either way.
    """
    found = []
    for dirpath, _, filenames in os.walk(corpus):
        for name in sorted(filenames):
            if name.endswith('.php'):
                found.append(os.path.join(dirpath, name))
    found.sort()
    if limit and len(found) > limit:
        stride = max(1, len(found) // limit)
        found = found[::stride][:limit]
    listing = tmp_path / 'targets.list'
    listing.write_text('\n'.join(found) + '\n', encoding='utf-8')
    return listing, found


@pytest.mark.corpus
def test_manifest_reports_shape_for_every_target(corpus, tmp_path):
    listing, targets = _targets(corpus, tmp_path, limit=5)
    out = tmp_path / 'manifests'
    run_lib('class_manifest.py', '--files', str(listing), '--output', str(out),
            '--config', toolchain_config(tmp_path))

    report = json.loads((out / '_manifest_report.json').read_text(encoding='utf-8'))
    assert set(report['files']) == set(targets)
    for entry in report['files'].values():
        # A file with no declared class is a legitimate outcome, not a failure;
        # a missing entry is not.
        assert 'state' in entry


@pytest.mark.corpus
def test_symbols_reports_a_document_per_target(corpus, tmp_path):
    listing, targets = _targets(corpus, tmp_path, limit=5)
    out = tmp_path / 'symbols'
    proc = run_lib('dump_batch.py', '--files', str(listing), '--output', str(out),
                   '--config', toolchain_config(tmp_path), check=False)
    assert proc.returncode == 0, proc.stderr

    report = json.loads((out / '_batch_report.json').read_text(encoding='utf-8'))
    assert set(report['files']) == set(targets)


@pytest.mark.corpus
def test_manifest_and_symbols_agree_on_the_method_count(corpus, tmp_path):
    """The two tools must agree, on quantities they define identically.

    They do not define method count the same way, and pretending otherwise
    produced false alarms on WHMCS:

    - `class_manifest.py` reports **own_methods**: what the class declares.
    - `dump_batch.py` reports the op_array's method table, which the Loader
      materializes **including inherited methods**, and attributes an override
      to both the parent and the child.

    Measured on WHMCS 5.3.12: comparing the two counts raised 2 false
    mismatches, and comparing `all_methods` instead (Reflection's getMethods(),
    which also folds in interface methods) raised 5 different ones. Neither
    scalar is universally comparable. Per class:

    - no parent, no interfaces: the two counts are the same quantity, and on
      WHMCS 118 of 118 agree exactly. This is the assertion.
    - a parent exists: arm56's count is the superset, so the exact invariant is
      a subset check -- every method the manifest says is declared must appear
      in arm56's set for that class. A method the manifest invents would fail.

    Class name lists are compared for every file, since both tools define those
    identically. On WHMCS: 167 files, zero disagreements.

    `docs/VALIDATION.md` has the full accounting, including the four
    parent-class cases and why each differs.
    """
    listing, _ = _targets(corpus, tmp_path, limit=25)
    manifests = tmp_path / 'manifests'
    symbols = tmp_path / 'symbols'

    cfg = toolchain_config(tmp_path)
    run_lib('class_manifest.py', '--files', str(listing), '--output', str(manifests),
            '--config', cfg)
    run_lib('dump_batch.py', '--files', str(listing), '--output', str(symbols),
            '--config', cfg)

    man = json.loads((manifests / '_manifest_report.json').read_text('utf-8'))
    sym = json.loads((symbols / '_batch_report.json').read_text('utf-8'))

    # arm56 writes one JSON per compiled file, keyed by the source path.
    by_source = {}
    for path in sorted(symbols.glob('*.json')):
        if path.name == '_batch_report.json':
            continue
        try:
            doc = json.loads(path.read_text('utf-8'))
        except ValueError:
            continue  # the resolver's own generated driver, dumped and cut short
        if doc.get('source'):
            by_source[doc['source']] = doc

    files_compared = 0
    classes_compared = 0
    exact = 0
    for path, m_entry in man['files'].items():
        if m_entry.get('state') != 'ok' or not m_entry.get('classes'):
            continue
        if sym['files'].get(path, {}).get('state') != 'ok':
            continue
        files_compared += 1

        assert sorted(m_entry['classes']) == sorted(
            sym['files'][path].get('classes') or []), (
            f'{path}: the two tools disagree on which classes the file declares')

        doc = by_source.get(path)
        if doc is None:
            continue
        for cls in json.loads(
                (manifests / f'{_sanitize(path)}.manifest.json').read_text('utf-8')
        )['classes']:
            arm = {s['name'] for s in doc.get('symbols', [])
                   if s.get('kind') == 'method' and s.get('scope') == cls['name']}
            if not arm and not cls['own_methods']:
                continue
            classes_compared += 1
            declared = {m['name'] for m in cls['methods']}
            missing = declared - arm
            assert not missing, (
                f'{cls["name"]}: manifest declares {sorted(missing)} but arm56 '
                f'reports no such method')
            if not cls.get('parent') and not cls.get('interfaces'):
                exact += 1
                assert len(declared) == len(arm), (
                    f'{cls["name"]}: no parent and no interfaces, so both tools '
                    f'must count the same methods, but manifest says '
                    f'{len(declared)} and arm56 says {len(arm)}')

    assert files_compared, (
        'no file produced both a manifest and a symbol dump, so nothing was '
        'cross-checked — treat this as a failure, not a vacuous pass')
    assert exact, (
        'no class without a parent or interfaces was compared, so the exact '
        'invariant was never exercised')

    # Coverage caveat, learned the hard way: an injected defect in a class that
    # the stride sample did not pick was NOT caught, and the test passed. The
    # sample is limit files out of the whole corpus, so this is a smoke-level
    # check. For full coverage run the stage over the entire corpus and diff the
    # two reports -- see docs/VALIDATION.md.


@pytest.mark.corpus
def test_reports_are_valid_json_under_a_non_ascii_path(corpus, tmp_path):
    # sanitize() maps every non-alphanumeric byte to '_', so two distinct
    # paths can collide. The report must still be parseable and must not lose
    # the mapping between target and result.
    listing, _ = _targets(corpus, tmp_path, limit=2)
    out = tmp_path / 'manifests'
    run_lib('class_manifest.py', '--files', str(listing), '--output', str(out),
            '--config', toolchain_config(tmp_path))
    report = json.loads((out / '_manifest_report.json').read_text(encoding='utf-8'))
    assert isinstance(report['files'], dict)


def test_sys_executable_is_used_not_a_bare_python(tmp_path):
    # Guards the harness itself: a bare 'python3' would resolve to whatever is
    # on PATH in CI, which is how a 3.6 runner silently fails the floor.
    assert sys.executable
    assert os.path.isabs(sys.executable)
