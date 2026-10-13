# Security and disclosure

## Scope

InkForge is independent ET-3850 research software. Its public scripts describe firmware parsing and a tested USB modification path for one `05.15.XB22Q5` printer. They do not establish remote access to other printers. New claims should identify the exact firmware, access required, test method, and observed device result.

## Report a new issue

- **InkForge code:** use GitHub's private vulnerability report for this repository if available. Do not put passwords, firmware images, or live exploit details in a public issue.
- **Epson product:** use [Epson's vulnerability report form](https://www.epson.eu/en_EU/faq/KA-01896). Include the model, firmware version, entry point, required access, minimal reproduction, observed and expected behavior, and a sanitized trace. Epson says it acknowledges reports within five working days and asks researchers to coordinate publication. It does not offer compensation.
- **Coordination help:** [CERT/CC](https://www.kb.cert.org/vuls/report/) asks researchers to contact the vendor first and may assist when coordination breaks down.

The [finding tracker](research/vulnerabilities.md) marks findings as live, offline, unverified, or retracted. Existing Epson advisories are linked there. A new report should distinguish a device observation from an inference about the code path; the [report template](research/disclosure-template.md) captures both.

This repository is public, and no Epson report for the custom-image acceptance finding has been submitted as of 2026-10-12. Public code and notes should not be treated as an Epson advisory or a statement that other versions are affected.
