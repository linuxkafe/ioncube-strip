"""
Shared fixtures for the integration suite.

Two tiers live here and they are not equally honest:

- The **tool-free** tests drive the real CLI and the real pipeline stages over
  synthetic inputs. They run everywhere, including CI, and they are the only
  tier that can regress in a normal pull request.
- The **toolchain** tests need PHP 5.6, the ionCube Loader and arm56. They skip
  when IONCUBE_STRIP_PHP56 / IONCUBE_STRIP_INI / IONCUBE_STRIP_ARM56 are unset.

There is no encrypted corpus in this repository, and there will not be one: a
fixture containing ionCube-encoded third-party code is a legal liability. The
toolchain tests therefore read a corpus from IONCUBE_STRIP_CORPUS, a directory
of .php files the operator supplies. A green run without those variables means
"the tool-free paths pass", never "the pipeline works on real input".
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI = os.path.join(ROOT, 'bin', 'ioncube-strip')
LIB = os.path.join(ROOT, 'lib')


def pytest_configure(config):
    config.addinivalue_line(
        'markers', 'toolchain: needs PHP 5.6 + ionCube Loader + arm56')
    config.addinivalue_line(
        'markers', 'corpus: needs IONCUBE_STRIP_CORPUS, a real encrypted tree')


def run(argv, cwd=None, check=True):
    """Run a command, returning the CompletedProcess.

    check=False is the caller's choice: the pipeline is expected to survive
    individual file failures, so some tests assert on non-zero exits.
    """
    proc = subprocess.run(argv, cwd=cwd or ROOT, capture_output=True,
                          check=check, text=True)
    return proc


def run_cli(*args, **kwargs):
    return run([CLI, *args], **kwargs)


def run_lib(script, *args, **kwargs):
    return run([sys.executable, os.path.join(LIB, script), *args], **kwargs)


def _env(name):
    value = os.environ.get(name, '')
    return value if value and os.path.exists(value) else ''


@pytest.fixture(scope='session')
def php56():
    value = _env('IONCUBE_STRIP_PHP56')
    if not value:
        pytest.skip('IONCUBE_STRIP_PHP56 not set; skipping toolchain test')
    return value


@pytest.fixture(scope='session')
def php56_ini():
    value = _env('IONCUBE_STRIP_INI')
    if not value:
        pytest.skip('IONCUBE_STRIP_INI not set; skipping toolchain test')
    return value


@pytest.fixture(scope='session')
def arm56_so():
    value = _env('IONCUBE_STRIP_ARM56')
    if not value:
        pytest.skip('IONCUBE_STRIP_ARM56 not set; skipping toolchain test')
    return value


@pytest.fixture(scope='session')
def corpus():
    """A directory of ionCube-encrypted .php files supplied by the operator."""
    value = os.environ.get('IONCUBE_STRIP_CORPUS', '')
    if not value or not os.path.isdir(value):
        pytest.skip('IONCUBE_STRIP_CORPUS not set; skipping corpus test')
    return value


@pytest.fixture(scope='session')
def php_argv(php56, php56_ini):
    return [php56, '-c', php56_ini]


# -- synthetic inputs ----------------------------------------------------
#
# Hand-built rather than committed, because the scan/pool stages are pure text
# processing and a checked-in fixture would be a second thing to keep in sync.

ENCRYPTED_HEADER = '<?php\n// 00e5 12 34 56 78 9a bc de f0\n$_il_exec();\n'
PLAIN_PHP = '<?php\nfunction ordinary() { return 1; }\n'


def write_hex_dump(path, text):
    """Write a dump in the shape lib/extract_pools.py actually parses.

    Two couplings are encoded here, and both are load-bearing:

    - the filename must contain `.fn.` — `discover_functions` globs `*.fn.*` and
      splits on it, so `render_0x1.txt` is invisible to the extractor;
    - every byte pair must be followed by a space, because the regex at
      lib/extract_pools.py:23 is `((?:[0-9a-f]{2} )+)` and therefore drops the
      final byte of a line that ends without one.

    A fixture that drifted from either would pass the test and fail in the
    field, so both are stated rather than left implicit.
    """
    lines = []
    for offset, start in enumerate(range(0, len(text), 16)):
        chunk = text[start:start + 16]
        pairs = ''.join(f'{b:02x} ' for b in chunk.encode('ascii'))
        lines.append(f'  {offset * 16:04x}: {pairs}')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')


def write_dump(root, source_file, func, offset, text):
    """Write one dump variant under the naming collect_dumps.py produces."""
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, f'{source_file}.fn.{func}_0x{offset}.txt')
    write_hex_dump(path, text)
    return path
