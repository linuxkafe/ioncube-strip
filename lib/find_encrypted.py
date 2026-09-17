#!/usr/bin/env python3
"""
find_encrypted.py — Recursively scan for ionCube-encrypted PHP files.

Usage: python3 find_encrypted.py [--config CONFIG] <source-root>
Output: newline-separated absolute paths to stdout

SPDX-License-Identifier: MIT
"""
import argparse
import os
import re

import yaml


def load_config(config_path):
    with open(config_path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def compile_markers(markers_config):
    compiled = []
    for m in markers_config:
        pattern = m['pattern']
        mtype = m.get('type', 'substring')
        if mtype == 'regex':
            compiled.append((re.compile(pattern), 'regex'))
        else:
            compiled.append((pattern, 'substring'))
    return compiled


def is_encrypted(filepath, markers):
    try:
        with open(filepath, 'rb') as fh:
            head = fh.read(200 * 1024)
    except OSError:
        return False
    text = head.decode('utf-8', errors='replace')
    for pattern, mtype in markers:
        if mtype == 'regex':
            if pattern.search(text):
                return True
        else:
            if pattern in text:
                return True
    return False


def scan(root, markers):
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.php'):
                continue
            fpath = os.path.join(dirpath, fname)
            if is_encrypted(fpath, markers):
                print(os.path.abspath(fpath))


def main():
    ap = argparse.ArgumentParser(description='Find ionCube-encrypted PHP files')
    ap.add_argument('source', help='Source directory to scan')
    ap.add_argument('--config', help='Path to ioncube-strip.yaml config file')
    args = ap.parse_args()

    config = {}
    if args.config:
        config = load_config(args.config)

    markers_config = config.get('markers', [
        {'pattern': '_il_exec', 'type': 'substring'},
        {'pattern': '//\\s*00e5', 'type': 'regex'},
    ])
    markers = compile_markers(markers_config)

    scan(args.source, markers)


if __name__ == '__main__':
    main()