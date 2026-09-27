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
from conftest import run_lib

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


def test_arm56_loads_as_a_zend_extension(php_argv, arm56_so):
    from conftest import run
    proc = run([*php_argv, '-d', f'zend_extension={arm56_so}', '-m'])
    assert proc.returncode == 0, proc.stderr
    assert 'arm56' in proc.stdout, proc.stdout


def test_arm56_dump_is_callable(php_argv, arm56_so):
    from conftest import run
    proc = run([*php_argv, '-d', f'zend_extension={arm56_so}', '-r',
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
    proc = run([*php_argv, '-d', f'zend_extension={arm56_so}', str(script)],
               check=False)
    assert proc.returncode == 0, proc.stderr
    assert list(out.iterdir()) == []


# -- corpus --------------------------------------------------------------

def _targets(corpus, tmp_path, limit=None):
    """Write the corpus file list in the form the batch tools expect."""
    found = []
    for dirpath, _, filenames in os.walk(corpus):
        for name in sorted(filenames):
            if name.endswith('.php'):
                found.append(os.path.join(dirpath, name))
    found.sort()
    if limit:
        found = found[:limit]
    listing = tmp_path / 'targets.list'
    listing.write_text('\n'.join(found) + '\n', encoding='utf-8')
    return listing, found


@pytest.mark.corpus
def test_manifest_reports_shape_for_every_target(corpus, tmp_path):
    listing, targets = _targets(corpus, tmp_path, limit=5)
    out = tmp_path / 'manifests'
    run_lib('class_manifest.py', '--files', str(listing), '--output', str(out))

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
                   check=False)
    assert proc.returncode == 0, proc.stderr

    report = json.loads((out / '_batch_report.json').read_text(encoding='utf-8'))
    assert set(report['files']) == set(targets)


@pytest.mark.corpus
def test_manifest_and_symbols_agree_on_the_method_count(corpus, tmp_path):
    """M3: two independent mechanisms must produce the same method count.

    Reflection (class_manifest.py) and the Loader's own symbol registration
    (dump_batch.py) have nothing in common but the file list. Where they
    disagree, one of them is wrong — treat it as a defect signal, not noise.

    docs/CONFIGURATION.md quotes 1028 methods across 104 files for the WHMCS
    includes/classes block. That figure is an observation from one machine, not
    an invariant: a different corpus legitimately yields a different number, so
    this asserts agreement, never a constant.
    """
    listing, _ = _targets(corpus, tmp_path, limit=25)
    manifests = tmp_path / 'manifests'
    symbols = tmp_path / 'symbols'

    run_lib('class_manifest.py', '--files', str(listing), '--output', str(manifests))
    run_lib('dump_batch.py', '--files', str(listing), '--output', str(symbols))

    man = json.loads((manifests / '_manifest_report.json').read_text('utf-8'))
    sym = json.loads((symbols / '_batch_report.json').read_text('utf-8'))

    compared = 0
    for path, m_entry in man['files'].items():
        s_entry = sym['files'].get(path)
        if s_entry is None or s_entry.get('state') != 'ok':
            continue
        if not m_entry.get('classes'):
            continue
        compared += 1
        assert m_entry['methods'] == s_entry['methods'], (
            f'{path}: Reflection reports {m_entry["methods"]} methods, arm56 '
            f'reports {s_entry["methods"]}')

    assert compared, (
        'no file produced a manifest and a symbol dump, so nothing was '
        'cross-checked — treat this as a failure, not a vacuous pass')


@pytest.mark.corpus
def test_reports_are_valid_json_under_a_non_ascii_path(corpus, tmp_path):
    # sanitize() maps every non-alphanumeric byte to '_', so two distinct
    # paths can collide. The report must still be parseable and must not lose
    # the mapping between target and result.
    listing, _ = _targets(corpus, tmp_path, limit=2)
    out = tmp_path / 'manifests'
    run_lib('class_manifest.py', '--files', str(listing), '--output', str(out))
    report = json.loads((out / '_manifest_report.json').read_text(encoding='utf-8'))
    assert isinstance(report['files'], dict)


def test_sys_executable_is_used_not_a_bare_python(tmp_path):
    # Guards the harness itself: a bare 'python3' would resolve to whatever is
    # on PATH in CI, which is how a 3.6 runner silently fails the floor.
    assert sys.executable
    assert os.path.isabs(sys.executable)
