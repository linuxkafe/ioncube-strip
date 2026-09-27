"""
Unit tests for probe_arm56.py — generation classification, no PHP required.

A fake `php` stands in for the real one: the classification reads a single line
of stdout, so the interesting behaviour is the mapping from that line to a
generation, and it is fully exercisable with a shell script.

The marker test matters because ARM56_VERSION lives in arm56.c. Bump the
extension's version without bumping V4_MARKER here and every `dump` run starts
refusing a perfectly good v4 build.
"""
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from lib.probe_arm56 import V4_MARKER, probe

ARM56_C = os.path.join(
    os.path.dirname(__file__), '..', '..', 'arm56', 'arm56.c')


def _fake_php(tmp_path, stdout='', returncode=0):
    """A `php` that ignores its arguments and prints one fixed line."""
    script = tmp_path / 'php'
    script.write_text(
        '#!/bin/sh\n'
        f"printf '%s' {shlex.quote(stdout)}\n"
        f'exit {returncode}\n', encoding='utf-8')
    script.chmod(0o755)
    return str(script)


def test_v4_extension_is_identified(tmp_path):
    php = _fake_php(tmp_path, f'arm56_version()={V4_MARKER}')
    assert probe(php, 'ini', 'arm56.so')['generation'] == 'v4'


def test_a_future_version_is_not_silently_called_v4(tmp_path):
    # arm56.c:35 is the only place the version is authoritative. An unexpected
    # value is reported as unknown, never optimistically as v4.
    php = _fake_php(tmp_path, 'arm56_version()=9.9.9')
    result = probe(php, 'ini', 'arm56.so')
    assert result['generation'] == 'unknown'
    assert result['version'] == '9.9.9'


def test_absence_of_the_marker_is_unverified_not_legacy(tmp_path):
    # The distinction is the whole point of the module: arm56_version() being
    # absent proves only that this is not the in-tree v4 build.
    php = _fake_php(tmp_path, 'arm56_version() absent')
    assert probe(php, 'ini', 'arm56.so')['generation'] == 'unverified'


def test_a_php_that_errors_is_unloadable(tmp_path):
    php = _fake_php(tmp_path, 'Warning: unable to load', returncode=1)
    result = probe(php, 'ini', 'arm56.so')
    assert result['generation'] == 'unloadable'
    assert 'unable to load' in result['detail']


def test_a_missing_php_binary_is_unloadable(tmp_path):
    result = probe(str(tmp_path / 'no-such-php'), 'ini', 'arm56.so')
    assert result['generation'] == 'unloadable'


def test_unrecognised_output_is_unloadable(tmp_path):
    php = _fake_php(tmp_path, 'something else entirely')
    assert probe(php, 'ini', 'arm56.so')['generation'] == 'unloadable'


def test_marker_matches_the_extension_source():
    with open(ARM56_C, encoding='utf-8') as fh:
        source = fh.read()
    match = re.search(r'#define\s+ARM56_VERSION\s+"([^"]+)"', source)
    assert match is not None, 'ARM56_VERSION not found in arm56/arm56.c'
    assert match.group(1) == V4_MARKER, (
        f'arm56.c declares {match.group(1)!r} but probe_arm56.V4_MARKER is '
        f'{V4_MARKER!r}; bump the marker with the extension')
