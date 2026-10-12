# Draft for vendor triage: XB22Q5 controller package reader can skip ECDSA finalization

**Status:** Offline finding in extracted ET-3850 XB22Q5 controller ARM code. The corrected CROM mapping now connects the LAN POST's first-stage `GetRequestID` request through ROM1 selection, a channel-1 body read, and the package receiver that calls this reader. The live controller reply, any earlier verifier, and physical update impact have not been demonstrated. This draft has not been submitted.

## Affected image and key behavior

The analyzed ET-3850 recovery RCX has SHA-256 `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675`; decoded controller segment 0 has SHA-256 `7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416`. The test printer reports version `05.15.XB22Q5`, but the decoded segment was extracted from a package and not dumped from the unit.

At `0x45778e40`, an `EPSONSIGNXB20d` header supplies a 32-bit declared payload length from offset `+0x10`. The routine copies the signature from that header and the P-256 public key from runtime address `0x4fb26800`. The signed-stream routine at `0x45778264` hashes read chunks and calls the verifier at `0x45778f0c` only when the remaining declared length reaches zero. The three-record package reader at `0x45778404` can return `1` after its third record while the remaining count is positive. Its immediate callers treat `1` as success.

## Minimal offline control

The ARM emulation below was rerun at the corrected CROM load base `0x4566ff74` with the same results. Function addresses elsewhere in this draft are provisional Ghidra addresses, 0x8c above runtime code addresses.

With the official three-record RCX and an isolated ARM emulator running the extracted reader/parser instructions, a verifier stub that always rejects is called once at the original declared size `40,603,648`, and the package reader returns `0`. Changing only the unsigned declared length to `40,603,649` causes the same reader to return `1`, leaves one byte in its count, and makes **zero** verifier calls. Hardware I/O, hash calculations, record-integrity checks, and staging operations are stubbed in this control. The source and exact reproduction conditions are in [`emulate_controller_reader_length.py`](../scripts/emulate_controller_reader_length.py) and the [research note](controller-signature-length-bypass.md).

An offline modified Wi-Fi image also recalculates the affected large-body 16-bit sum and SHA-1 digest, then appends a byte so the declared and actual RCX payload lengths agree. Its unchanged ECDSA signature fails against the currently extracted IPL public key, while all six body sums and three record digests pass in an independent Python implementation. With this candidate, the same isolated ARM reader returns `1` and never invokes the verifier. The candidate file is kept outside the repository; no payload was sent to a printer.

## Security question and suggested fix

If a production update route hands untrusted RCX bytes to this reader without an earlier full-package signature check, this control flow could accept altered firmware despite the P-256 signature. A separate first-IPL path sets its stream state to `2` after a valid first record (`0x266a4` / `0x26898`) when a memory-mapped mode byte at `0x82c00000` equals `2`; its finalizer at raw offset `0x9614` then rejects a positive remaining-byte count before its own P-256 decision. A route passing through that finalizer in mode `2` would stop this candidate. The live mode byte, route order, and flash commit remain unproved, so device-level severity is not assigned.

The first-IPL update callback table is statically recoverable from its startup copy descriptor: RAM `0x463297ac` maps to IPL offset `0x287bc`, and callback `+0x0c` resolves to the `0x9614` finalizer. Early boot branches through `0x3108` to update entry `0x85ec` when mode selector `0xd58` returns nonzero. The first-IPL update routine at `0x8f60` then calls the finalizer slot when its status byte differs from `5`. This confirms a conditional boot route, but still does not connect the ROM1 network transfer to that routine or identify its live mode. [The dispatch checker](../scripts/inspect_ipl0_update_dispatch.py) reproduces the table and branches.

The [hash-checked controller chain](../scripts/inspect_controller_update_chain.py) recovers the callback table from the first IPL's startup copy descriptor. ROM1 callback `0x12` queues the package source, while callback `0x11` supplies a read function that calls controller D4 channel `1`; the package source later queues the receiver that invokes this reader. This raises confidence that the decoded code path is relevant to the network update, but it does not substitute for observing an accepted transfer on the test device.

Require signed-stream state `verified` and a zero remaining-byte count before the package reader reports success or commits staged content. Reject declared lengths that disagree with the complete three-record payload. Authenticate the full package before staging or flashing any record. Test both a length that matches the three records and a length one byte larger, including an appended trailing byte.
