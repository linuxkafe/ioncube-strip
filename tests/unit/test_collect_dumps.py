"""
Unit tests for collect_dumps.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from lib.collect_dumps import collect_dumps


def test_collect_dumps():
    with tempfile.TemporaryDirectory() as tmpdir:
        source_root = os.path.join(tmpdir, 'source')
        output_root = os.path.join(tmpdir, 'output')
        arm56_tmp = os.path.join(tmpdir, 'arm56_tmp')

        os.makedirs(os.path.join(source_root, 'includes'))
        os.makedirs(arm56_tmp)

        # Create test encrypted file
        encrypted_file = os.path.join(source_root, 'includes', 'functions.php')
        with open(encrypted_file, 'w') as f:
            f.write('<?php // 00e5\n?>')

        # Create fake arm56 dump files
        # arm56 uses _<abs_path_from_root_with_underscores>.fn.<func>_0x<addr>.txt
        file_abs = os.path.abspath(encrypted_file)
        rel_from_root = os.path.relpath(file_abs, '/')
        dump_prefix = '_' + rel_from_root.replace('/', '_') + '.fn.'
        open(os.path.join(arm56_tmp, dump_prefix + 'func1_0x1000.txt'), 'w').close()
        open(os.path.join(arm56_tmp, dump_prefix + 'func1_0x2000.txt'), 'w').close()
        open(os.path.join(arm56_tmp, dump_prefix + 'func2_0x1000.txt'), 'w').close()

        result = collect_dumps(source_root, encrypted_file, output_root, arm56_tmp)
        assert result is True

        # Check output structure
        assert os.path.exists(os.path.join(output_root, 'dumps', 'includes', 'functions.php.fn.func1_0x1000.txt'))
        assert os.path.exists(os.path.join(output_root, 'dumps', 'includes', 'functions.php.fn.func1_0x2000.txt'))
        assert os.path.exists(os.path.join(output_root, 'dumps', 'includes', 'functions.php.fn.func2_0x1000.txt'))

        # Check arm56 tmp was cleaned
        assert not os.path.exists(os.path.join(arm56_tmp, dump_prefix + 'func1_0x1000.txt'))


def test_collect_dumps_no_dumps():
    with tempfile.TemporaryDirectory() as tmpdir:
        source_root = os.path.join(tmpdir, 'source')
        output_root = os.path.join(tmpdir, 'output')
        arm56_tmp = os.path.join(tmpdir, 'arm56_tmp')

        os.makedirs(os.path.join(source_root, 'includes'))
        os.makedirs(arm56_tmp)

        encrypted_file = os.path.join(source_root, 'includes', 'functions.php')
        with open(encrypted_file, 'w') as f:
            f.write('<?php // 00e5\n?>')

        result = collect_dumps(source_root, encrypted_file, output_root, arm56_tmp)
        assert result is False


if __name__ == '__main__':
    test_collect_dumps()
    test_collect_dumps_no_dumps()
    print("All tests passed")