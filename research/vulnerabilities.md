# Vulnerability tracking

| Finding | Evidence | Status | Impact on modification work |
| --- | --- | --- | --- |
| Initial Web Config administrator password can be derived through SNMP when unchanged | [Epson advisory CVE-2025-35970](https://epson.ca/support/wa00965) names ET-3850. A single read-only SNMP query and one login succeeded on the test device. Serial/password are omitted here. | **Known issue, reproduced locally.** Not a new disclosure. | Grants Web Config administrator access, but no arbitrary file write or shell was identified. |
| ENUP debug authentication | Extracted firmware contains an RSA public key, `/tmp/enup_auth_success` trigger, and a one-time-password comparison. | **Protected service; no bypass found.** | Telnet does not start merely because Web Config administrator login succeeds. |
| Certificate import | Authenticated Web Config exposes `/PRESENTATIONEX/CERT/IMPORT_CHAIN` for certificate and key files. The ARM route table maps it to handler `0x226474`; that handler checks a fixed list of return paths, parses `format`, `id`, `cert0`-`cert2`, and `key`, then calls internal certificate APIs. | **Investigated; no arbitrary path or code execution demonstrated.** | A legitimate upload writes certificate material through fixed APIs; it cannot be treated as access to `/opt/nwsoc_data/ExtBoot` without proof. |
| Web Config CSRF | [Epson advisory CVE-2026-58315](https://www.epson.co.uk/en_GB/faq/KA-02075) lists ET-3850. | **Known issue; not tested locally.** | Settings modification through a victim browser is not arbitrary code execution. |

## Reporting threshold

Promote a research lead to a report only after reproducing it on this firmware version with a minimal proof, identifying the affected route and impact, and showing a reversible test. Do not include the printer's serial number, administrator password, Wi-Fi credentials, or proprietary firmware binaries in a public report.

Epson's [vulnerability disclosure policy](https://www.epson.eu/en_EU/faq/KA-01896) provides the reporting route for a **new, undisclosed** issue. The SNMP/default-password and CSRF issues above already have Epson advisories and should not be submitted as novel findings. No new vulnerability is confirmed in this repository.
