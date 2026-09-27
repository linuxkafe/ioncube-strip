"""
Unit tests for the declared PHP floor.

Every .php file in this repository must parse and run under PHP 5.6: the
dumpers are executed by the 5.6 binary, and the ionCube Loader is a 5.x-era
zend_extension. The quality gate lints with `php -l` on whatever PHP 8.x the
machine happens to have, which is structurally incapable of catching a 7.0+
construct — it accepts it.

The bug this exists for: lib/dump_one.php used `$argv[1] ?? ''`. The null
coalescing operator is PHP 7.0. Under 5.6 that is a parse error, so the
headline `ioncube-strip dump` subcommand failed on every input while every
documented gate passed.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Constructs newer than PHP 5.6, as (pattern, first version providing it).
#
# The patterns are deliberately blunt: false positives cost a comment rewrite,
# false negatives cost a broken `dump` run on every encrypted file.
POST_56_PHP = [
    (r'\?\?', '7.0'),
    (r'\?->', '7.0'),
    (r'<=>', '7.0'),
    (r'\bdeclare\s*\(\s*strict_types', '7.0'),
    (r'\bfunction\s+\w+\s*\([^)]*\)\s*:\s*\??\w', '7.0'),
    (r'\b(?:public|private|protected)?\s*const\s+\w+\s*=', '7.1'),
    (r'\biterable\b', '7.1'),
    (r'\bvoid\b\s*;|\)\s*:\s*void', '7.1'),
    (r'\bcatch\s*\([^)]*\|\s*', '7.1'),
]

# Newer constructs that need a shape check rather than a bare token, because the
# token itself is a legal PHP 5.6 word.
POST_56_PHP_STRICT = [
    (r'\bstr_contains\s*\(', '8.0'),
    (r'\bstr_starts_with\s*\(', '8.0'),
    (r'\bstr_ends_with\s*\(', '8.0'),
    (r'\barray_key_first\s*\(', '7.3'),
    (r'\barray_key_last\s*\(', '7.3'),
    (r'\bjson_last_error_msg\s*\(', '7.3'),
]


def _php_files():
    for sub in ('lib', 'tests'):
        base = os.path.join(ROOT, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for name in sorted(filenames):
                if name.endswith('.php'):
                    yield os.path.join(dirpath, name)


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def _strip_php_strings_and_comments(source):
    """Blank out comments and string literals, keeping line numbers intact.

    Without this, a docblock that says "does not use ??" would fail the scan,
    and the test would train contributors to avoid documenting the constraint.
    """
    out = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ''
        if ch == '/' and nxt == '/' or ch == '#':
            while i < n and source[i] != '\n':
                out.append(' ')
                i += 1
        elif ch == '/' and nxt == '*':
            while i < n and not (source[i] == '*' and i + 1 < n
                                 and source[i + 1] == '/'):
                out.append('\n' if source[i] == '\n' else ' ')
                i += 1
            out.append('  ')
            i += 2
        elif ch in '"\'':
            quote = ch
            out.append(' ')
            i += 1
            while i < n:
                if source[i] == '\\':
                    out.append('  ')
                    i += 2
                    continue
                if source[i] == quote:
                    out.append(' ')
                    i += 1
                    break
                out.append('\n' if source[i] == '\n' else ' ')
                i += 1
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def test_shipped_php_files_exist():
    # A silently empty file list would make every test below vacuously pass.
    found = list(_php_files())
    assert found, 'no .php files found under lib/ or tests/'
    assert any(path.endswith('dump_one.php') for path in found)


def test_no_post_56_syntax_in_shipped_php():
    for path in _php_files():
        code = _strip_php_strings_and_comments(_read(path))
        rel = os.path.relpath(path, ROOT)
        for pattern, version in POST_56_PHP:
            hit = re.search(pattern, code)
            assert hit is None, (
                f'{rel} matches {pattern!r} (PHP {version}) but every shipped '
                f'.php file must parse under PHP 5.6')


def test_no_post_56_functions_in_shipped_php():
    for path in _php_files():
        code = _strip_php_strings_and_comments(_read(path))
        rel = os.path.relpath(path, ROOT)
        for pattern, version in POST_56_PHP_STRICT:
            hit = re.search(pattern, code)
            assert hit is None, (
                f'{rel} calls {pattern!r} (PHP {version}) but every shipped '
                f'.php file must run under PHP 5.6')


def test_documented_floor_is_56():
    # The floor is asserted in docs/INSTALL.md and the CONFIGURATION.md notes.
    install = _read(os.path.join(ROOT, 'docs', 'INSTALL.md'))
    assert '5.6' in install
