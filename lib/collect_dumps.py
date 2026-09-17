#!/usr/bin/env python3
"""
collect_dumps.py — Collect arm56 output files and mirror to output directory.

Usage: python3 collect_dumps.py --source <source-root> --file <encrypted-file> --output <output-root> [--arm56-tmp /tmp/arm56_output]

After dump_one.php executes a file, arm56 writes dumps to ARM56_TMP.
This script finds those dumps and copies them to output-root/dumps/<rel-path>.fn.*

SPDX-License-Identifier: MIT
"""
import argparse
import glob
import os
import shutil
import sys

import yaml


def load_config(config_path):
    with open(config_path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def collect_dumps(source_root, encrypted_file, output_root, arm56_tmp):
    """Copy arm56 dumps for one file to mirrored output structure."""
    try:
        rel_path = os.path.relpath(encrypted_file, source_root)
    except ValueError:
        print(f"Error: {encrypted_file} not under {source_root}", file=sys.stderr)
        return False

    # arm56 produces files like: _home_user_project_path_to_file.php.fn.funcname_0x1234.txt
    file_abs = os.path.abspath(encrypted_file)

    # Build the prefix arm56 uses: _<absolute_path_with_underscores>.fn.
    rel_from_root = os.path.relpath(file_abs, '/')
    prefix = '_' + rel_from_root.replace('/', '_') + '.fn.'

    # Find all matching dump files
    pattern = os.path.join(arm56_tmp, prefix + '*')
    dump_files = glob.glob(pattern)

    if not dump_files:
        return False

    # Create output directory mirroring source structure
    out_dir = os.path.join(output_root, 'dumps', os.path.dirname(rel_path))
    os.makedirs(out_dir, exist_ok=True)

    # Copy with simplified naming: <rel_path>.fn.<func>_0x*.txt
    base_name = os.path.basename(rel_path)
    for dump_file in dump_files:
        dump_base = os.path.basename(dump_file)
        # Extract the function part after .fn.
        if '.fn.' in dump_base:
            fn_part = dump_base.split('.fn.', 1)[1]
            out_name = base_name + '.fn.' + fn_part
            out_path = os.path.join(out_dir, out_name)
            shutil.copy2(dump_file, out_path)

    # Clean up arm56 tmp directory
    for dump_file in dump_files:
        try:
            os.remove(dump_file)
        except OSError:
            pass

    return True


def main():
    ap = argparse.ArgumentParser(description='Collect arm56 dumps for a single file')
    ap.add_argument('--source', required=True, help='Source root directory')
    ap.add_argument('--file', required=True, help='Encrypted file that was dumped')
    ap.add_argument('--output', required=True, help='Output root directory')
    ap.add_argument('--arm56-tmp', help='arm56 output directory (default: from config or /tmp/arm56_output)')
    ap.add_argument('--config', help='Path to ioncube-strip.yaml config file')
    args = ap.parse_args()

    config = {}
    if args.config:
        config = load_config(args.config)

    toolchain = config.get('toolchain', {})
    arm56_tmp = args.arm56_tmp or toolchain.get('arm56_tmp', '/tmp/arm56_output')

    success = collect_dumps(args.source, args.file, args.output, arm56_tmp)
    if not success:
        print(f"No dumps collected for {args.file}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()