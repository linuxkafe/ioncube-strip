"""
Unit tests for stub_resolver.py — the parts that do not need PHP.

The resolver's contract is subtle: a stub must be declared with the kind the
Loader named, a skip must match its own stub line, and PHP class names are
case-insensitive while the fatal that triggers a skip lowercases them. These
tests pin that behaviour so it cannot be broken silently.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from lib.stub_resolver import (
    MISSING_RE,
    REDECLARE_RE,
    STUB_PREAMBLE,
    STUB_TEMPLATES,
    StubResolver,
    sanitize,
)


def test_missing_regex_captures_kind_and_name():
    text = ("Fatal error: Interface 'WHMCS_Payment_Filter_FilterInterface' not "
            "found in /x/AbstractFilter.php on line 0")
    found = MISSING_RE.findall(text)
    assert found == [('Interface', 'WHMCS_Payment_Filter_FilterInterface')]


def test_missing_regex_handles_class_and_trait():
    assert MISSING_RE.findall("Class 'WHMCS_Foo' not found") == [('Class', 'WHMCS_Foo')]
    assert MISSING_RE.findall("Trait 'WHMCS_Bar' not found") == [('Trait', 'WHMCS_Bar')]


def test_missing_regex_ignores_unrelated_errors():
    assert MISSING_RE.findall("Fatal error: Call to undefined function foo()") == []


def test_redeclare_regex_matches_both_spellings():
    assert REDECLARE_RE.findall(
        "Cannot redeclare class whmcs_listtable in /x.php") == ['whmcs_listtable']
    assert REDECLARE_RE.findall(
        "Cannot declare class Foo because the name is already in use") == ['Foo']


def test_stub_templates_encode_the_loader_kind():
    # The kind matters: PHP rejects "implements X" if X was declared as a class.
    assert STUB_TEMPLATES['Interface'].format(name='Foo') == 'interface Foo {}'
    assert STUB_TEMPLATES['Class'].format(name='Foo') == 'abstract class Foo {}'
    assert STUB_TEMPLATES['Trait'].format(name='Foo') == 'trait Foo {}'


def test_stub_preamble_declares_exactly_what_it_is_given():
    # The driver evals whole lines; a format placeholder left in the PHP would
    # declare a class literally named "%s".
    assert 'eval($line);' in STUB_PREAMBLE
    assert "'%s '" not in STUB_PREAMBLE
    assert '@include' not in STUB_PREAMBLE, 'suppression hides the symbol name'


def test_sanitize_is_filesystem_safe_and_stable():
    assert sanitize('/a/b/c.php') == '_a_b_c.php'
    assert sanitize('/a/b/c.php') == sanitize('/a/b/c.php')
    assert '/' not in sanitize('/x/y')
    assert ' ' not in sanitize('/x y')


def test_classify_prefers_learned_stubs():
    r = StubResolver('php', 'ini', [], '/tmp')
    r.stubs['WHMCS_Known'] = 'interface WHMCS_Known {}'
    missing, redeclared = r._classify(
        "Interface 'WHMCS_Known' not found\n"
        "Interface 'WHMCS_New' not found\n"
        "Cannot redeclare class WHMCS_Shadow in /x.php")
    # Already-known symbols are not re-learned; the new one is.
    assert missing == {('Interface', 'WHMCS_New')}
    assert redeclared == {'WHMCS_Shadow'}


def test_counts_summarises_states():
    r = StubResolver('php', 'ini', [], '/tmp')
    r.status = {'a': {'state': 'ok'}, 'b': {'state': 'ok'}, 'c': {'state': 'missing'}}
    assert r.counts() == {'ok': 2, 'missing': 1}


def test_run_removes_its_scratch_directory(tmp_path, monkeypatch):
    # One attempt per file per round, so an unremoved mkdtemp leaks a directory
    # for every file in the batch. /bin/true stands in for PHP: the point is
    # the scratch lifecycle, not what PHP prints.
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(tempfile, 'tempdir', str(scratch))

    r = StubResolver('/bin/true', 'ini', [], str(tmp_path))
    result = r._run(str(tmp_path / 'target.php'), STUB_PREAMBLE, str(tmp_path))

    assert len(result) == 3
    assert result[0] == 0
    assert list(scratch.iterdir()) == []


def test_run_returns_a_triple_even_on_timeout(tmp_path, monkeypatch):
    # The scratch dir must be cleaned on the timeout path too, and the return
    # shape must not vary or the caller unpacking breaks.
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(tempfile, 'tempdir', str(scratch))

    hanging_php = tmp_path / 'php'
    hanging_php.write_text('#!/bin/sh\nexec sleep 30\n')
    hanging_php.chmod(0o755)

    r = StubResolver(str(hanging_php), 'ini', [], str(tmp_path), timeout=1)
    result = r._run(str(tmp_path / 'target.php'), STUB_PREAMBLE, str(tmp_path))

    assert len(result) == 3
    assert result == (None, '', '')
    assert list(scratch.iterdir()) == []
