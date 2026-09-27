"""
Tool-free integration tests — the CLI and the text-processing stages, driven
end to end over synthetic inputs.

These need no PHP 5.6, no arm56 and no encrypted corpus, so they are the tier
that actually regresses in CI. What they do not cover is stated in
test_extraction.py; keeping the two apart stops a green run from being read as
"the pipeline works on real input".
"""
import json
import os

import pytest
from conftest import (
    ENCRYPTED_HEADER,
    PLAIN_PHP,
    run_cli,
    run_lib,
    write_dump,
)

CONFIG = os.path.join('config', 'ioncube-strip.yaml.example')


@pytest.fixture
def source_tree(tmp_path):
    """A directory with two marker-bearing files and one plain file."""
    root = tmp_path / 'src'
    (root / 'pkg').mkdir(parents=True)
    (root / 'a.php').write_text(ENCRYPTED_HEADER, encoding='utf-8')
    (root / 'pkg' / 'b.php').write_text(ENCRYPTED_HEADER, encoding='utf-8')
    (root / 'pkg' / 'plain.php').write_text(PLAIN_PHP, encoding='utf-8')
    return root


# -- scan ----------------------------------------------------------------

def test_cli_scan_finds_only_encrypted_files(source_tree, tmp_path):
    listing = tmp_path / 'files.list'
    proc = run_cli('scan', '--source', str(source_tree),
                   '--output', str(listing))

    assert proc.returncode == 0, proc.stderr
    found = {os.path.basename(line) for line in
             listing.read_text(encoding='utf-8').split()}
    assert found == {'a.php', 'b.php'}


def test_cli_scan_without_output_writes_to_stdout(source_tree):
    proc = run_cli('scan', '--source', str(source_tree))
    assert proc.returncode == 0, proc.stderr
    assert 'a.php' in proc.stdout


# -- pool ----------------------------------------------------------------

@pytest.fixture
def dumps_tree(tmp_path):
    """Synthetic arm56 output: two variants of one function, one of another."""
    root = str(tmp_path / 'dumps')
    write_dump(root, 'a.php', 'render', 1, 'SELECT id FROM tbl\x00WHERE name = ?')
    write_dump(root, 'a.php', 'render', 2, 'ORDER BY id DESC')
    write_dump(root, 'a.php', 'connect', 1, 'mysql_connect')
    return root


def test_cli_pool_writes_pools_and_index(dumps_tree, tmp_path):
    out = tmp_path / 'work'
    proc = run_cli('pool', '--dumps', str(dumps_tree), '--output', str(out))

    assert proc.returncode == 0, proc.stderr
    index = json.loads((out / 'pools' / '_index.json').read_text(encoding='utf-8'))
    assert set(index) == {'render', 'connect'}


def test_pool_unions_variants_per_function(dumps_tree, tmp_path):
    # The two render variants hold different halves of one statement; both must
    # land in the same pool, or the extractor is not unioning.
    out = tmp_path / 'work'
    run_lib('extract_pools.py', '--dumps', str(dumps_tree), '--output', str(out),
            '--config', CONFIG)

    render = (out / 'pools' / 'render.txt').read_text(encoding='utf-8')
    assert 'SELECT id FROM tbl' in render
    assert 'ORDER BY id DESC' in render
    assert 'mysql_connect' not in render


def test_pool_deduplicates_identical_runs_across_variants(tmp_path):
    # Dedup is by whole run, not by word: ascii_runs() returns maximal runs, so
    # 'dup dup dup dup' is one 15-byte string, not four. The dedup that matters
    # is the same run arriving from two dump variants of one function.
    root = str(tmp_path / 'dumps')
    write_dump(root, 'a.php', 'render', 1, 'SELECT id\x00LIMIT 1')
    write_dump(root, 'a.php', 'render', 2, 'SELECT id\x00LIMIT 1')
    out = tmp_path / 'work'

    run_lib('extract_pools.py', '--dumps', root, '--output', str(out),
            '--config', CONFIG)

    assert (out / 'pools' / 'render.txt').read_text(
        encoding='utf-8').splitlines() == ['SELECT id', 'LIMIT 1']


def test_pool_reports_no_dumps_without_crashing(tmp_path):
    empty = tmp_path / 'dumps'
    empty.mkdir()
    proc = run_lib('extract_pools.py', '--dumps', str(empty),
                   '--output', str(tmp_path / 'work'), '--config', CONFIG,
                   check=False)
    assert proc.returncode == 0, proc.stderr
    assert 'No dump files found' in proc.stderr


# -- argument handling ---------------------------------------------------

@pytest.mark.parametrize('command', ['scan', 'dump', 'pool', 'manifest', 'symbols'])
def test_every_subcommand_rejects_a_bare_invocation(command):
    proc = run_cli(command, check=False)
    assert proc.returncode == 1
    assert 'ERROR:' in proc.stderr


def test_manifest_dry_run_names_the_manifest_stage(tmp_path):
    listing = tmp_path / 'files.list'
    listing.write_text('a.php\n', encoding='utf-8')

    proc = run_cli('manifest', '--files', str(listing),
                   '--output', str(tmp_path / 'out'), '--dry-run')

    assert proc.returncode == 0, proc.stderr
    assert '[DRY-RUN]' in proc.stdout
    assert 'class_manifest.py' in proc.stdout
    assert not (tmp_path / 'out').exists(), 'dry run created output'


def test_symbols_dry_run_names_the_symbol_stage(tmp_path):
    listing = tmp_path / 'files.list'
    listing.write_text('a.php\n', encoding='utf-8')

    proc = run_cli('symbols', '--files', str(listing),
                   '--output', str(tmp_path / 'out'), '--dry-run')

    assert proc.returncode == 0, proc.stderr
    assert 'dump_batch.py' in proc.stdout
    assert not (tmp_path / 'out').exists(), 'dry run created output'


def test_manifest_rejects_a_missing_file_list(tmp_path):
    proc = run_cli('manifest', '--files', str(tmp_path / 'nope.list'),
                   '--output', str(tmp_path / 'out'), check=False)
    assert proc.returncode == 1
    assert 'File list not found' in proc.stderr


def test_unknown_command_and_option_are_refused():
    assert run_cli('frobnicate', check=False).returncode == 1
    assert run_cli('scan', '--wat', check=False).returncode == 1


def test_help_lists_every_subcommand():
    proc = run_cli('--help')
    assert proc.returncode == 0
    for command in ('scan', 'dump', 'pool', 'manifest', 'symbols', 'run'):
        assert command in proc.stdout, f'{command} missing from --help'

# -- run flag forwarding -------------------------------------------------


def test_run_does_not_dry_run_unless_asked(source_tree, tmp_path):
    """Regression: `run` put every stage into dry-run mode unconditionally.

    `${dry_run:+--dry-run}` expands whenever the variable is *set*, and dry_run
    is set to 0 when the flag is absent. `run` therefore printed [DRY-RUN] and
    wrote no scan.list even with no --dry-run flag, and the printed [DRY-RUN]
    line made that look deliberate.
    """
    out = tmp_path / 'work'
    proc = run_cli('run', '--source', str(source_tree), '--output', str(out), check=False)

    # It will still fail at the toolchain check without PHP 5.6, but it must
    # have reached the scan stage first.
    assert '[DRY-RUN]' not in proc.stdout
    assert (out / 'scan.list').exists(), 'run did not actually scan'
    assert 'a.php' in (out / 'scan.list').read_text(encoding='utf-8')


def test_run_dry_run_creates_nothing(source_tree, tmp_path):
    out = tmp_path / 'work'
    proc = run_cli(
        'run', '--source', str(source_tree), '--output', str(out), '--dry-run', check=False
    )
    assert '[DRY-RUN]' in proc.stdout
    assert not out.exists(), 'dry run created output'


# -- verbose -------------------------------------------------------------


def test_verbose_produces_output_and_default_does_not(source_tree, tmp_path):
    plain = run_cli('scan', '--source', str(source_tree), '--output', str(tmp_path / 'a.list'))
    loud = run_cli(
        'scan', '--source', str(source_tree), '--output', str(tmp_path / 'b.list'), '--verbose'
    )

    assert plain.returncode == loud.returncode == 0
    assert '[verbose]' not in plain.stderr
    assert '[verbose]' in loud.stderr


def test_verbose_reports_the_resolved_config(source_tree, tmp_path):
    proc = run_cli(
        'scan', '--source', str(source_tree), '--output', str(tmp_path / 'a.list'), '--verbose'
    )
    assert str(source_tree) in proc.stderr
    assert 'ioncube-strip.yaml.example' in proc.stderr
