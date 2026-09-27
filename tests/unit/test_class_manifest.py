"""
Unit tests for class_manifest.py — report assembly, no PHP required.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from lib.class_manifest import DRIVER_BODY, manifest_path, read_manifest


def test_driver_reports_manifest_on_stdout():
    # The resolver captures stdout; a driver that only wrote to a file would
    # silently produce an empty report.
    assert 'json_encode($out)' in DRIVER_BODY
    assert 'echo json_encode' in DRIVER_BODY


def test_driver_does_not_use_php7_only_reflection():
    # hasType()/getReturnType() do not exist in PHP 5.6 and raise at runtime.
    assert 'hasType(' not in DRIVER_BODY
    assert 'getReturnType(' not in DRIVER_BODY


def test_driver_guards_parameter_class_lookup():
    # A type hint naming an unloadable class makes getClass() throw, which
    # would abort the whole file's manifest.
    assert 'try {' in DRIVER_BODY
    assert 'catch (ReflectionException' in DRIVER_BODY


def test_driver_only_counts_own_members():
    # getMethods() includes everything inherited; own_methods must be filtered
    # or a marker class looks like it declares Exception's methods.
    assert "getDeclaringClass()->getName() !== $c" in DRIVER_BODY


def test_read_manifest_missing_file(tmp_path):
    assert read_manifest(str(tmp_path), '/nope/Missing.php') is None


def test_read_manifest_rejects_unparseable(tmp_path):
    path = manifest_path(str(tmp_path), '/a/broken.php')
    with open(path, 'w') as fh:
        fh.write('{"classes": [')
    assert read_manifest(str(tmp_path), '/a/broken.php') is None


def test_read_manifest_rejects_wrong_shape(tmp_path):
    path = manifest_path(str(tmp_path), '/a/other.php')
    with open(path, 'w') as fh:
        json.dump({'stage': 'symbols'}, fh)
    assert read_manifest(str(tmp_path), '/a/other.php') is None


def test_read_manifest_accepts_valid(tmp_path):
    path = manifest_path(str(tmp_path), '/a/good.php')
    with open(path, 'w') as fh:
        json.dump({'file': '/a/good.php', 'classes': [{'name': 'Foo'}]}, fh)
    doc = read_manifest(str(tmp_path), '/a/good.php')
    assert doc is not None
    assert doc['classes'][0]['name'] == 'Foo'
