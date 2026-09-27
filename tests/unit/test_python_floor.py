"""
Unit tests for the declared Python version floor.

The project documents Python 3.8+ in four places. Nothing in the toolchain
enforces that claim: ruff's target-version stops ruff from *recommending* 3.9+
APIs but reports no rule for a 3.9+ call already in the code. These tests pin
the claim so the docs and the code cannot drift apart again.

The bug this exists for: lib/extract_pools.py called str.removesuffix(), which
is 3.9+, while README.md, docs/INSTALL.md and CLAUDE.md all promised 3.8+.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Runtime APIs newer than the floor, as (pattern, first version providing it).
#
# The patterns match attribute and module access rather than bare identifiers:
# the bug this exists for was `x.removesuffix(...)`, which a `(?<![\w.])`
# guard on the bare name would not catch. Each pattern is anchored on a call
# or an import so a prose mention of the name in a comment does not trip it.
POST_38_APIS = [
    (r'\.removesuffix\s*\(', '3.9'),
    (r'\.removesprefix\s*\(', '3.9'),
    (r'(?<![\w.])removesuffix\s*\(', '3.9'),
    (r'(?<![\w.])removesprefix\s*\(', '3.9'),
    (r'\bmath\.lcm\b', '3.9'),
    (r'\bfunctools\.cache\b', '3.9'),
    (r'\b(?:import|from)\s+graphlib\b', '3.9'),
    (r'\b(?:import|from)\s+zoneinfo\b', '3.9'),
    (r'\.bit_count\s*\(', '3.10'),
    (r'\bitertools\.pairwise\b', '3.10'),
    (r'\bhashlib\.file_digest\b', '3.11'),
    (r'\btyping\.Self\b', '3.11'),
]


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding='utf-8') as fh:
        return fh.read()


def _lib_sources():
    lib = os.path.join(ROOT, 'lib')
    for name in sorted(os.listdir(lib)):
        if name.endswith('.py'):
            path = os.path.join(lib, name)
            with open(path, encoding='utf-8') as fh:
                yield name, fh.read()


def test_ruff_declares_the_documented_floor():
    # The linter must be told the floor, or it suggests code that breaks it.
    assert 'target-version = "py38"' in _read('pyproject.toml')


def test_docs_agree_on_the_floor():
    # All four documents claim 3.8+; if one is updated, the rest must follow.
    for relpath in ('README.md', 'docs/INSTALL.md', 'CLAUDE.md'):
        assert '3.8+' in _read(relpath), f'{relpath} no longer states the floor'


def test_no_post_38_runtime_apis_in_lib():
    # ruff will not do this, so the check is explicit and deliberately narrow:
    # these patterns are the plausible ones to reach for, not an exhaustive
    # ban. A new entry to POST_38_APIS extends the net; it is not a proof.
    for name, source in _lib_sources():
        for pattern, version in POST_38_APIS:
            hit = re.search(pattern, source)
            assert hit is None, (
                f'lib/{name} matches {pattern!r} (Python {version}) but the '
                f'documented floor is 3.8')


def test_lib_compiles():
    # A syntax error, or 3.9+ syntax, breaks the floor. py_compile against the
    # running interpreter catches the latter only if that interpreter is old,
    # so this is a sanity net rather than the primary gate.
    lib = os.path.join(ROOT, 'lib')
    proc = subprocess.run(
        [sys.executable, '-m', 'compileall', '-q', lib],
        capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr.decode('utf-8', 'replace')
