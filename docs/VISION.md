# ioncube-strip — Vision

## Problem

IonCube-encoded PHP software from the 2005-2015 era (PHP 5.0-5.6) is increasingly unmaintainable:
- Original vendors have disappeared or stopped supporting legacy versions
- License servers have been shut down, making legitimate installations inoperable
- Source code was never released; only ionCube-encrypted binaries exist
- PHP 5.6 reached EOL in 2018; modern servers run PHP 8.x

Organizations running such software face a crisis: **rewrite from scratch** (expensive, risky) or **recover the source** from encrypted files.

## Solution

`ioncube-strip` is an **offline, zero-network toolkit** that extracts literal strings (function names, class names, error messages, SQL queries, config keys) from ionCube 5.x encrypted PHP files by executing them under a PHP 5.6 runtime instrumented with the `arm56` extension.

The `arm56` extension hooks the ionCube VM at runtime and snapshots the shared literal buffer (`RESERVED[3]`), producing per-function hex dumps. `ioncube-strip` collects these dumps, parses the hex, extracts printable ASCII runs, deduplicates them, and outputs clean **literal pools** — one file per function.

These pools are the raw material for **manual source reconstruction**. A developer reads the pool, understands the function's intent, and writes a PHP 8.x compatible implementation. No decompilation, no AST reconstruction, no control flow analysis — just the literals that the original code *had* to contain.

## Value Proposition

| For... | Value |
|--------|-------|
| **Abandoned software maintainers** | Recover business logic without vendor cooperation |
| **License recovery** | Restore legally licensed installations after license server death |
| **Digital preservation** | Archive readable artifacts from encrypted cultural heritage |
| **Security researchers** | Analyze obfuscated malware/backdoors from PHP 5.x era |

## Non-Goals

- **Not a decompiler** — No control flow, no variable reconstruction, no AST
- **Not for ionCube 6.x/10.x/12.x** — Different VM, different encryption
- **Not automated reconstruction** — Human judgment required
- **Not a license bypass** — Requires valid ionCube file + PHP 5.6 runtime
- **Not a distributed system** — Single-machine, offline operation