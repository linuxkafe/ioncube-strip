# ioncube-strip — Legal Notice

## License

This project is licensed under the **MIT License** — see `LICENSE` file for details.

SPDX-License-Identifier: MIT

## Third-Party Components

| Component | License | Purpose |
|-----------|---------|---------|
| `arm56` extension | Proprietary (ionCube) | Runtime dumping — **NOT included** |
| PHP 5.6 | PHP License v3.01 | Runtime for dumps — **NOT included** |
| PyYAML | MIT | Configuration parsing |
| ruff | MIT | Python linting (dev only) |

**This repository does NOT include:**
- ionCube loader or decoder
- arm56 extension source or binary
- PHP 5.6 binaries
- Any encrypted PHP files

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