"""
Unit tests for extract_pools.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from lib.extract_pools import ascii_runs, discover_functions, parse_hex_dump


def test_parse_hex_dump():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("""[RESERVED[3]=
  00001000: 68 65 6c 6c 6f 20 77 6f 72 6c 64 00 00 00 00 00
  00001010: 74 65 73 74 5f 73 74 72 69 6e 67 00 00 00 00 00
""")
        fname = f.name
    try:
        raw = parse_hex_dump(fname)
        assert b'hello world' in raw
        assert b'test_string' in raw
    finally:
        os.unlink(fname)


def test_ascii_runs():
    raw = b'hello world\x00\x00test_string\x00another string'
    runs = ascii_runs(raw, minlen=3, maxlen=2000, charset='ascii')
    decoded = [r.decode('ascii') for r in runs]
    assert 'hello world' in decoded
    assert 'test_string' in decoded
    assert 'another string' in decoded


def test_ascii_runs_minlen():
    raw = b'ab\x00hello\x00xy'
    runs = ascii_runs(raw, minlen=3, maxlen=2000, charset='ascii')
    decoded = [r.decode('ascii') for r in runs]
    assert 'hello' in decoded
    assert 'ab' not in decoded
    assert 'xy' not in decoded


def test_ascii_runs_maxlen():
    raw = b'a' * 2500
    runs = ascii_runs(raw, minlen=3, maxlen=2000, charset='ascii')
    # re.findall finds non-overlapping matches: 2000 + 500 = 2 matches
    assert len(runs) == 2
    assert len(runs[0]) == 2000
    assert len(runs[1]) == 500


def test_discover_functions():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test dump files
        open(os.path.join(tmpdir, 'test.fn.func1_0x1000.txt'), 'w').close()
        open(os.path.join(tmpdir, 'test.fn.func1_0x2000.txt'), 'w').close()
        open(os.path.join(tmpdir, 'test.fn.func2_0x1000.txt'), 'w').close()
        os.makedirs(os.path.join(tmpdir, 'subdir'))
        open(os.path.join(tmpdir, 'subdir', 'test.fn.func3_0x1000.txt'), 'w').close()

        func_files = discover_functions(tmpdir)
        assert 'func1' in func_files
        assert 'func2' in func_files
        assert 'func3' in func_files
        assert len(func_files['func1']) == 2
        assert len(func_files['func2']) == 1
        assert len(func_files['func3']) == 1


def test_cli_extract_pools():
    """Test CLI extract_pools on fixture dumps."""
    import subprocess
    fixture_dir = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'dumps')
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run([
            sys.executable,
            os.path.join(os.path.dirname(__file__), '..', '..', 'lib', 'extract_pools.py'),
            '--dumps', fixture_dir,
            '--output', tmpdir
        ], capture_output=True, text=True, check=False)

        assert result.returncode == 0

        # Check output files
        pools_dir = os.path.join(tmpdir, 'pools')
        assert os.path.exists(os.path.join(pools_dir, 'func1.txt'))
        assert os.path.exists(os.path.join(pools_dir, 'func2.txt'))
        assert os.path.exists(os.path.join(pools_dir, '_index.json'))

        # Check index content
        with open(os.path.join(pools_dir, '_index.json')) as f:
            index = json.load(f)
        assert 'func1' in index
        assert 'func2' in index
        assert index['func1']['variants'] == 2
        assert index['func2']['variants'] == 1


if __name__ == '__main__':
    test_parse_hex_dump()
    test_ascii_runs()
    test_ascii_runs_minlen()
    test_ascii_runs_maxlen()
    test_discover_functions()
    test_cli_extract_pools()
    print("All tests passed")