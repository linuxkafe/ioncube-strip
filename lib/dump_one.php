<?php
/**
 * dump_one.php — Execute a single ionCube-encrypted file under PHP 5.6 + arm56.
 *
 * The legacy arm56 extension hooks function entry and writes the RESERVED[3]
 * literal buffers to the directory named by toolchain.arm56_tmp in the
 * config. The in-tree v4 extension does not do this: it writes JSON to
 * ARM56_JSON and exposes arm56_dump(). See docs/CONFIGURATION.md,
 * "Two arm56 generations".
 *
 * Usage: php dump_one.php <file.php>
 *
 * @package ioncube-strip
 * @license MIT
 */

// SPDX-License-Identifier: MIT

// Not `$argv[1] ?? ''`: the null coalescing operator is PHP 7.0+ and this file
// runs under PHP 5.6, where it is a parse error. `php -l` on the 8.x used by
// the lint gate cannot catch that, so tests/unit/test_php56_syntax.py does.
$file = isset($argv[1]) ? $argv[1] : '';
if (!$file || !is_file($file)) {
    fwrite(STDERR, "Usage: php dump_one.php <file.php>\n");
    exit(1);
}

// Simply include the file; arm56 hooks fire on function entry
include $file;