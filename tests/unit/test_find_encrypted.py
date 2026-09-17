"""
Unit tests for find_encrypted.py
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from lib.find_encrypted import compile_markers, is_encrypted


def test_compile_markers():
    markers_config = [
        {'pattern': '_il_exec', 'type': 'substring'},
        {'pattern': r'^//\s*00e5', 'type': 'regex'},
    ]
    compiled = compile_markers(markers_config)
    assert len(compiled) == 2
    assert compiled[0][1] == 'substring'
    assert compiled[1][1] == 'regex'


def test_is_encrypted_substring():
    markers = [('_il_exec', 'substring')]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False) as f:
        f.write('<?php _il_exec("test"); ?>')
        fname = f.name
    try:
        assert is_encrypted(fname, markers) is True
    finally:
        os.unlink(fname)


def test_is_encrypted_regex():
    markers = [(re.compile(r'//\s*00e5'), 'regex')]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False) as f:
        f.write('<?php // 00e5\nfunction foo() {} ?>')
        fname = f.name
    try:
        assert is_encrypted(fname, markers) is True
    finally:
        os.unlink(fname)


def test_is_not_encrypted():
    markers = [('_il_exec', 'substring')]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False) as f:
        f.write('<?php function foo() {} ?>')
        fname = f.name
    try:
        assert is_encrypted(fname, markers) is False
    finally:
        os.unlink(fname)


def test_cli_scan():
    """Test CLI scan command on fixture directory."""
    fixture_dir = os.path.join(os.path.dirname(__file__), '..', 'fixtures')
    result = subprocess.run([
        sys.executable,
        os.path.join(os.path.dirname(__file__), '..', '..', 'lib', 'find_encrypted.py'),
        fixture_dir
    ], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    output = result.stdout.strip().split('\n')
    # Should find encrypted_with_marker.php and encrypted_with_header.php
    assert len(output) == 2
    for path in output:
        assert 'encrypted_with_marker.php' in path or 'encrypted_with_header.php' in path
        assert 'plain.php' not in path


if __name__ == '__main__':
    test_compile_markers()
    test_is_encrypted_substring()
    test_is_encrypted_regex()
    test_is_not_encrypted()
    test_cli_scan()
    print("All tests passed")