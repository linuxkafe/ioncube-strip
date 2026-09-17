<?php
/**
 * dump_one.php — Execute a single ionCube-encrypted file under PHP 5.6 + arm56.
 *
 * The arm56 extension hooks function entry and writes RESERVED[3] literal buffers
 * to /tmp/arm56_output/ (or configured ARM56_TMP).
 *
 * Usage: php dump_one.php <file.php>
 *
 * @package ioncube-strip
 * @license MIT
 */

// SPDX-License-Identifier: MIT

$file = $argv[1] ?? '';
if (!$file || !is_file($file)) {
    fwrite(STDERR, "Usage: php dump_one.php <file.php>\n");
    exit(1);
}

// Simply include the file; arm56 hooks fire on function entry
include $file;