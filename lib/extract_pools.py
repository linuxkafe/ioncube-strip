#!/usr/bin/env python3
"""
extract_pools.py — Extract literal pools from arm56 hex dumps.

Usage: python3 extract_pools.py --dumps <dumps-dir> --output <pools-dir> [--config CONFIG]

Reads all *.fn.* files under dumps-dir, extracts printable ASCII runs from hex dumps,
deduplicates per function, writes pools/<func>.txt and pools/_index.json

SPDX-License-Identifier: MIT
"""
import argparse
import glob
import json
import multiprocessing
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import yaml

HEX_LINE = re.compile(r'^  [0-9a-f]{4,8}: ((?:[0-9a-f]{2} )+)', re.MULTILINE)


def load_config(config_path):
    with open(config_path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def parse_hex_dump(path):
    """Extract raw bytes from arm56 hex dump file."""
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return b''
    raw = b''
    for m in HEX_LINE.finditer(text):
        try:
            raw += bytes(int(x, 16) for x in m.group(1).split())
        except ValueError:
            pass
    return raw


def ascii_runs(raw, minlen=3, maxlen=2000, charset='ascii'):
    """Extract printable runs from raw bytes."""
    if charset == 'ascii':
        pattern = rb'[\x20-\x7e]{%d,%d}' % (minlen, maxlen)
    else:
        pattern = rb'[\x20-\x7e]{%d,%d}' % (minlen, maxlen)
    return re.findall(pattern, raw)


def process_function(args):
    """Process all dump variants for a single function."""
    func_name, dump_files, minlen, maxlen, charset = args
    seen = []
    seen_set = set()
    total_bytes = 0

    for dump_file in dump_files:
        raw = parse_hex_dump(dump_file)
        total_bytes += len(raw)
        for run in ascii_runs(raw, minlen, maxlen, charset):
            try:
                s = run.decode('ascii', 'replace')
            except UnicodeDecodeError:
                continue
            if s in seen_set or len(s) > maxlen:
                continue
            seen_set.add(s)
            seen.append(s)

    return func_name, len(dump_files), total_bytes, len(seen), seen


def discover_functions(dumps_root):
    """Find all unique function names from dump filenames."""
    pattern = os.path.join(dumps_root, '**', '*.fn.*')
    files = glob.glob(pattern, recursive=True)
    func_files = {}
    for f in files:
        basename = os.path.basename(f)
        if '.fn.' not in basename:
            continue
        parts = basename.split('.fn.', 1)
        if len(parts) != 2:
            continue
        fn_part = parts[1]
        func_name = fn_part.split('_0x')[0]
        func_name = func_name.removesuffix('.txt')
        func_files.setdefault(func_name, []).append(f)
    return func_files


def main():
    ap = argparse.ArgumentParser(description='Extract literal pools from arm56 dumps')
    ap.add_argument('--dumps', required=True, help='Directory containing dump files')
    ap.add_argument('--output', required=True, help='Output directory for pools')
    ap.add_argument('--config', help='Path to ioncube-strip.yaml config file')
    ap.add_argument('--workers', type=int, help='Number of worker processes (0=auto)')
    args = ap.parse_args()

    config = {}
    if args.config:
        config = load_config(args.config)

    extraction = config.get('extraction', {})
    minlen = extraction.get('min_run_length', 3)
    maxlen = extraction.get('max_run_length', 2000)
    charset = extraction.get('charset', 'ascii')
    workers = args.workers if args.workers is not None else extraction.get('workers', 0)
    if workers <= 0:
        workers = multiprocessing.cpu_count()

    os.makedirs(args.output, exist_ok=True)
    pools_dir = os.path.join(args.output, 'pools')
    os.makedirs(pools_dir, exist_ok=True)

    func_files = discover_functions(args.dumps)
    if not func_files:
        print("No dump files found", file=sys.stderr)
        return

    tasks = [
        (name, files, minlen, maxlen, charset)
        for name, files in func_files.items()
    ]

    index = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for func_name, nvar, nbytes, nruns, runs in executor.map(process_function, tasks):
            out_path = os.path.join(pools_dir, f'{func_name}.txt')
            with open(out_path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(runs) + '\n')
            index[func_name] = {
                'variants': nvar,
                'raw_bytes': nbytes,
                'runs': nruns
            }
            print(f"{func_name:32s} variants={nvar:3d} runs={nruns:5d}", flush=True)

    index_path = os.path.join(pools_dir, '_index.json')
    with open(index_path, 'w', encoding='utf-8') as fh:
        json.dump(index, fh, indent=2, sort_keys=True)


if __name__ == '__main__':
    main()