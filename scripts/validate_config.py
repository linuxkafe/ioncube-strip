#!/usr/bin/env python3
"""Validate ioncube-strip.yaml config schema.

Exits non-zero on the first problem. The checks are explicit rather than
assert-based: `python3 -O` strips asserts, which would turn a validator into a
no-op exactly when it matters.
"""
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = ['toolchain', 'markers', 'output', 'extraction', 'parallelism']


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, 'config', 'ioncube-strip.yaml.example')

    if not os.path.isfile(path):
        print(f'FAIL: config not found: {path}', file=sys.stderr)
        return 1

    with open(path, encoding='utf-8') as fh:
        cfg = yaml.safe_load(fh) or {}

    missing = [section for section in REQUIRED if section not in cfg]
    if missing:
        for section in missing:
            print(f'FAIL: missing section: {section}', file=sys.stderr)
        return 1

    print(f'Config schema valid: {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
