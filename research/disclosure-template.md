# Vulnerability report template

Send a new Epson product finding through [Epson's report form](https://www.epson.eu/en_EU/faq/KA-01896). Use this structure to keep measured facts separate from a proposed explanation. [CERT/CC](https://www.kb.cert.org/vuls/report/) recommends contacting the vendor first; [GitHub's coordinated disclosure guidance](https://docs.github.com/en/code-security/concepts/vulnerability-reporting-and-management/coordinated-disclosure) also describes private reporting before a detailed public writeup.

## Summary

- One-sentence issue and security consequence:
- Product and exact firmware version:
- Access required: USB / same LAN / routed network / authenticated account / none:
- Current status: reproduced on device / offline emulation / static analysis:

## Reproduction

1. Starting device state and configuration:
2. Minimal input or action (attach sanitized bytes or script privately):
3. Actual result, including timing, logs, and repeat count:
4. Expected result:
5. Recovery or rollback performed:

## Evidence and limits

- Firmware/package hash and code location:
- Device evidence independent of a transport acknowledgement:
- Controls that rule out ordinary behavior or an unrelated restart:
- What the data **does not** establish:
- Other models or versions tested (write “none” if none):

## Impact and remedy

- Confidentiality, integrity, or availability consequence:
- Proposed fix or validation rule:
- Suggested regression test:

## Coordination record

- Date sent, vendor case ID, acknowledgement:
- Private evidence supplied and redactions applied:
- Vendor response and retest result:
- Agreed publication date and credit:

Remove serial numbers, administrator and root passwords, Wi-Fi settings, private IPs, and proprietary firmware binaries unless the vendor specifically needs them through a secure channel.
