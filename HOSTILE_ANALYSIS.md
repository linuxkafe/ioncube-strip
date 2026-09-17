# ioncube-strip — Hostile Analysis (Phase 1)

## INSIGHTS CONSULTED
- `/home/seyon/dev/whmcs/ioncube-strip/` (existing implementation)
- `/home/seyon/dev/whmcs/scripts/` (batch dump scripts)
- `/home/seyon/dev/whmcs/aes/kanban.md` (project context)

## ASSUMPTIONS I'M MAKING

### [KNOWN] — Facts with direct evidence
- ionCube encryption for PHP 5.x uses a marker `// 00e5` or function `_il_exec` in file headers
- The arm56 extension (PHP 5.6) hooks into the ionCube VM and dumps `RESERVED[3]` literal buffers to `/tmp/arm56_output/`
- arm56 requires PHP 5.6 CLI with specific headers; cannot run on PHP 7+
- The existing codebase works for WHMCS 5.3.x but has hardcoded paths (`/home/seyon/`, `/tmp/arm56_output/`)
- `extract_pools.py` unions printable ASCII runs across all dump variants per function
- Pool extraction is deterministic given same input dumps

### [INFERRED] — Conclusions from evidence chains
- The tool is specific to ionCube format used in WHMCS 5.x era (PHP 5.0-5.6)
- Different ionCube versions may have different markers or RESERVED buffer layouts
- The hardcoded WHMCS paths in `extract_pools.py` (PREFIX) make it non-reusable for other projects
- Parallel processing in `extract_pools.py` uses all CPU cores — good for throughput
- The bash driver `ioncube-strip.sh` assumes a specific directory layout (dumps/, pools/)

### [ASSUMED] — Beliefs with potential impact if false
- Target users have access to PHP 5.6 + arm56 build environment (non-trivial setup)
- Users want offline, zero-network de-obfuscation (no license server calls)
- The literal pool output is sufficient for manual reconstruction (no auto-decompilation)
- PHP 8.4 is the target reconstruction runtime (per WHMCS project)

### [UNKNOWN] — Areas outside reliable knowledge
- Whether arm56 works on ionCube 10+ encoded files (likely not)
- Compatibility with non-WHMCS ionCube-encrypted codebases
- Whether literal pools alone suffice for complex control flow reconstruction
- Legal implications in different jurisdictions (reverse engineering for interoperability vs. license evasion)

## WHAT WASN'T SPECIFIED (that matters)
- Target audience: developers doing license-recovery vs. security researchers vs. archivists
- Whether to support multiple ionCube versions (5.x, 6.x, 10.x)
- Whether to provide a reconstruction stub generator (Phase 2 feature)
- Distribution method: pip, Homebrew, Docker, raw release binaries
- Test corpus: need known-encrypted samples for CI validation

## ALTERNATIVES I DIDN'T CHOOSE (and why)

| Option | Description | Rejected Because |
|--------|-------------|------------------|
| **Static decompiler** | Build a full ionCube VM decompiler in Python/Go | Multi-year research project; ionCube VM is obfuscated and changes per version |
| **Dynamic analysis only** | Just run files and trace execution (like PHP-Parser + Xdebug) | Requires valid license server; defeats "abandoned software recovery" use case |
| **Wrap existing tools** | Package `ioncube_decoder` or commercial decoders | Proprietary, expensive, often require network; violates "offline recovery" goal |
| **Support PHP 7+ ionCube** | Extend to newer ionCube versions | arm56 is PHP 5.6 only; newer versions need different loader hooks |
| **GUI/Web interface** | Visual pool browser | Scope creep; CLI is sufficient for target workflow (manual reconstruction) |

## INVITE CONTRADICTION
- **What would disprove my reasoning?**
  - If a working static decompiler for ionCube 5.x exists → my "static decompiler rejected" is wrong
  - If arm56 works on PHP 7+ with minor patches → my "PHP 5.6 only" assumption is wrong
  - If literal pools are insufficient for >80% of functions → the whole approach is flawed
  - If legal counsel says this violates DMCA 1201 in US → project cannot be published publicly

- **Critical flaw I might be missing:**
  The tool assumes the *exact same* ionCube encoding as WHMCS 5.3.x. Other projects using ionCube 5.x may use different encoder options (optimization level, obfuscation flags) that change the RESERVED buffer layout or markers.

## DISTINGUISH CLAIM TYPES

### Empirical (what is)
- "arm56 extracts RESERVED[3] from ionCube 5.x" — verifiable by running on test file
- "Pool extraction produces deduplicated ASCII strings" — verifiable by inspecting output
- "PHP 5.6 + arm56 is required runtime" — verifiable by build matrix

### Normative (what should be)
- "Tool should be project-agnostic (not WHMCS-specific)" — design choice
- "Output should be consumable for manual reconstruction" — workflow assumption
- "No network access ever" — security/privacy requirement
- "Publish on GitHub without .aes/aes" — distribution policy

## RISKS & SIDE EFFECTS
1. **Hardcoded paths break portability** — Current code has `/home/seyon/`, WHMCS-specific prefixes
2. **arm56 build is fragile** — Requires PHP 5.6 headers, specific GCC version; may not build on modern distros
3. **No test suite** — Cannot verify correctness without known encrypted samples
4. **Single-output format** — Only produces literal pools; no AST, no CFG, no symbol table
5. **Legal exposure** — DMCA 1201 (US), EUCD Art. 6 (EU) anti-circumvention provisions
6. **Maintenance burden** — ionCube is abandoned tech; tool will bit-rot

## COST OF BEING WRONG: HIGH
- If tool only works for WHMCS → wasted effort generalizing
- If legal issues → GitHub takedown, liability
- If arm56 doesn't build → tool is unusable for new users
- If pools insufficient → false promise of "recovery"

## REASONING SKELETON FOR KEY CLAIMS

**Claim: "Offline runtime dumping via arm56 is the only viable approach"**
- Premise 1: ionCube 5.x uses a VM with encrypted bytecode — static analysis fails
- Premise 2: The VM must decrypt literals at runtime to execute — arm56 hooks this
- Premise 3: Commercial decoders require license server → online, not for abandoned software
- Inference: Runtime dumping with a custom extension is the only offline method
- Conclusion: Build tool around arm56 + pool extraction

**Claim: "Generalizing beyond WHMCS requires removing hardcoded paths"**
- Premise 1: Current `extract_pools.py` has WHMCS-specific PREFIX constant
- Premise 2: `ioncube-strip.sh` assumes specific output directory structure
- Premise 3: Target is "recover abandoned software" (plural) not just WHMCS
- Inference: Must parameterize all paths, markers, output formats
- Conclusion: Rewrite as configurable, project-agnostic toolkit

## SCOPE BOUNDARIES DECLARATION

**IN SCOPE:**
- Recursive scan for ionCube 5.x markers (`_il_exec`, `// 00e5`)
- Driver script to execute each file under PHP 5.6 + arm56
- Configurable toolchain paths (PHP binary, INI, arm56.so, output dir)
- Pool extractor: configurable input/output, parallel processing, dedup
- CLI interface with help, version, dry-run
- Documentation: install, usage, limitations, legal notice
- Unit tests for pool extraction logic (with synthetic dumps)
- CI pipeline (lint, test, build)

**OUT OF SCOPE (explicitly excluded):**
- arm56 extension source/build — external dependency
- PHP 5.6 toolchain provisioning — user responsibility
- Static decompilation / control flow reconstruction
- GUI, web UI, or IDE integration
- Support for ionCube 6.x, 10.x, 12.x
- License key extraction or bypass
- Automated code reconstruction from pools
- Docker image (can be added later as separate artifact)