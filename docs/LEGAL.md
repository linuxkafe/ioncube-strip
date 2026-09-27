# ioncube-strip — Legal Notice

## License

This project is licensed under the **MIT License** — see `LICENSE` file for details.

SPDX-License-Identifier: MIT

## Third-Party Components

| Component | License | Purpose | Included here |
|-----------|---------|---------|---------------|
| `arm56` v4 extension (`arm56/arm56.c`, `arm56/config.m4`) | MIT (SPDX header in source) | Serialises the `zend_op_array` the Loader materialises, to JSON | **Yes** — first-party source in this repository |
| Legacy `arm56` extension | See its own distribution | The original hex-dump runtime dumping this project was built around | **No** — must be obtained separately |
| ionCube Loader | ionCube proprietary | Required at runtime to decode anything | **No** |
| PHP 5.6 | PHP License v3.01 | Runtime | **No** |
| PyYAML | MIT | Configuration parsing | Dependency, not vendored |
| ruff | MIT | Python linting (dev only) | Dependency, not vendored |

**This repository does NOT include:**
- The ionCube Loader, or any decoder
- The legacy arm56 extension (source or binary)
- PHP 5.6 binaries
- Any ionCube-encrypted PHP files, real or synthetic
- Any build artifacts of the arm56 extension (`.libs/`, `modules/`, `*.lo`)

### A note on the two arm56 extensions

Do not conflate them. The v4 extension in this repository is **first-party
MIT-licensed source** written for this project; it is not ionCube code and
carries no ionCube license. The *legacy* extension that this project was
originally built around is third-party, is **not** included here, and its
redistribution and licensing terms are entirely the user's responsibility to
satisfy. `python3 lib/probe_arm56.py` tells you which one you have loaded;
see `docs/CONFIGURATION.md`, "Two arm56 generations".

If you obtained the legacy extension from a third party, verify its license
before redistributing it or incorporating it into anything you ship.

## Intended Use

`ioncube-strip` is designed for **legitimate recovery scenarios**:

1. **Abandoned software maintenance** — Vendor gone, license server dead, legitimate license held
2. **License recovery** — Restoring legally purchased software after license infrastructure loss
3. **Digital preservation** — Archiving readable artifacts from encrypted cultural heritage
4. **Security research** — Analyzing obfuscated PHP malware/backdoors (with authorization)
5. **Interoperability** — Understanding data formats for migration (EU Software Directive Art. 6)

## Prohibited Use

**Do NOT use this tool for:**
- Circumventing active license enforcement on currently supported software
- Unauthorized access to proprietary systems
- Redistributing recovered source code without rights holder permission
- Creating competing products from recovered code
- Any activity violating DMCA 1201 (US), EUCD Art. 6 (EU), or local anti-circumvention laws

## Legal Risk Disclaimer

**THE AUTHORS PROVIDE THIS TOOL "AS IS" WITHOUT WARRANTY OF ANY KIND.**

- ionCube encryption is a **technical protection measure** under DMCA 1201 / EUCD Art. 6
- Circumventing it **may be illegal** in your jurisdiction, even for interoperability
- The "interoperability exception" (DMCA 1201(f), EUCD Art. 6) is **narrow and fact-specific**
- **Consult legal counsel** before using on code you do not own or have explicit rights to

## User Responsibilities

By using `ioncube-strip`, you agree:

1. You have **lawful possession** of the encrypted files
2. You have **valid license rights** to the underlying software (if applicable)
3. You will **not distribute** recovered source code without authorization
4. You **accept all legal risk** for your use of this tool
5. You will **indemnify** the authors against claims arising from your use

## Jurisdiction-Specific Notes

### United States (DMCA 1201)
- Librarian of Congress exemptions (2021, 2024) cover **preservation of abandoned software** and **security research**
- Exemptions require: lawfully obtained, not for commercial advantage, good faith
- **No blanket exemption** — each use case must qualify

### European Union (EUCD Art. 6 / DSM Directive Art. 15)
- Art. 6(1) allows decompilation for **interoperability** under strict conditions
- DSM Directive Art. 15 allows **text and data mining** for research
- National implementations vary — check local law

### Other Jurisdictions
- Canada (CMA), Australia (Copyright Act), Japan (UCPA) have similar provisions
- **Verify local law** before proceeding

## Ethical Guidelines

- **Attribute** recovered code to original authors if identifiable
- **Contribute back** fixes/improvements to community forks if software is community-maintained
- **Report vulnerabilities** found during analysis responsibly
- **Respect** the intent of original developers (obfuscation ≠ malice)

## No Legal Advice

**THIS DOCUMENT IS NOT LEGAL ADVICE.** It is a summary of known considerations.
**CONSULT A QUALIFIED ATTORNEY** in your jurisdiction before using this tool on any codebase.

## Reporting

If you believe this tool infringes your rights, contact the maintainers via GitHub Issues.
We will respond in good faith and remove/amend as appropriate.