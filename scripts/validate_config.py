#!/usr/bin/env python3
"""Validate ioncube-strip.yaml config schema."""
import sys
import yaml

with open('config/ioncube-strip.yaml.example') as f:
    cfg = yaml.safe_load(f)

required = ['toolchain', 'markers', 'output', 'extraction', 'parallelism']
for r in required:
    assert r in cfg, f'Missing section: {r}'
print('Config schema valid')