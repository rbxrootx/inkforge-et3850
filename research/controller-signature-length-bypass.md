# Controller signed-stream length bypass: offline reproduction

**Status:** The decoded XB22Q5 ARM controller reader returns success without calling its ECDSA verifier when the unsigned `EPSONSIGNXB20d` declared payload length exceeds the bytes consumed by its three package records. This is reproduced in isolated ARM emulation. A static ROM1 network chain now reaches this reader through D4 channel 1; live image acceptance, any earlier authentication gate, and a successful flash on an ET-3850 remain unproved. No modified package was sent to the printer.

## How the key and length gate work

The signature-header parser at `0x45778e40` copies the P-256 public key from running-IPL RAM `0x4fb26800` to `0x45d660e4`, and copies the 64-byte RCX signature to `0x45d66124`. It reads a 32-bit little-endian payload length from signature-header offset `+0x10`; it checks only that this length is nonzero. The key and signature header sit outside the bytes hashed for the RCX signature. Replacing the key inside an incoming image does not replace this runtime key.

The signed-stream routine at `0x45778264` decrements that declared length as it hashes payload chunks. It calls the P-256 verifier at `0x45778f0c` **only when the remaining count reaches zero**. A read that leaves a positive count returns the read/hash helper's success value without making a signature decision.

The package reader at `0x45778404` reads **three** IPL records. On success it returns `1` without checking that the signed-stream state reached verified state `2` or that its remaining count is zero. In mode `0xb`, it makes one final raw callback call; in the other modes it drains the raw input callback. Neither path feeds that tail through the signed-stream verifier. Callers `ControllerPackageReceiver` at `0x45777488` and `FUN_45778a88` at `0x45778a88` treat a return value of `1` as success. No independent signature check was identified in those immediate callers.

## Reproduction

Use a separately obtained XB22Q5 RCX (SHA-256 `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675`) and decoded controller segment 0 (SHA-256 `7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416`). The repository does not contain either binary. Install the Python `unicorn` package, then run:

```text
python scripts/emulate_controller_reader_length.py controller-0.bin FWCJ61TL.rcx --compare-plus-one
```

The script executes the extracted ARM signature-header parser, signed-stream routine, IPL record parser, type gate, and three-record reader at the corrected CROM load base `0x4566ff74`. It stubs hardware I/O, hash calculations, record-integrity checks, and staging operations. The verifier stub always rejects so the control shows whether it is reached:

| Declared length | Reader result | Remaining bytes | ECDSA calls |
| ---: | ---: | ---: | ---: |
| 40,603,648 (original) | `0` | `0` | `1` |
| 40,603,649 (one larger) | `1` | `1` | `0` |

The RCX's three records end exactly at the original payload boundary. An offline Wi-Fi candidate replaces the second SquashFS, recalculates its enclosing record's large-body 16-bit sum and SHA-1 digest, increments the unsigned signature-header length to 40,603,649, appends one zero byte, and changes the unsigned `[Z_1]` size by one. This makes the declared and actual payload lengths agree while the three-record reader still stops before the appended byte. Its file SHA-256 is `428e3c4052b4f678c33818f1151618868672a85b5275e6df293ad2cc30385bdf`. The file stays in scratch space outside this repository.

The candidate's original ECDSA signature is **invalid** against the public key in the current IPL, and its embedded key is unchanged. [`check_rcx_against_current_ipl.py`](../scripts/check_rcx_against_current_ipl.py) reports rejection. Nonetheless, the isolated controller reader returns `1`, with one byte remaining and zero ECDSA calls. The ARM-emulator stubs report that all three record-integrity call sites were reached. Independently, [`check_controller_record_integrity.py`](../scripts/check_controller_record_integrity.py) computes the checks on the original and candidate packages: all six 16-bit byte sums (one for each short and large body) and all three SHA-1 record digests match their headers. The digest rule decompiled from `0x45778cc8` and `0x45778d14` is `SHA1(large_body || SHA1(first_14_header_bytes))`. The large-body sum is copied into the later staging metadata at `0x45728d8c`; it is not checked by the three-record reader itself. The [offline candidate builder](../scripts/build_length_gate_candidate.py) reproduces the changed SquashFS, record sum, digest, length, and optional trailing byte from user-supplied firmware files.

## Limits and next gate

The emulator stubs the record checks and flash staging, while the separate Python check reproduces the record math. It does not emulate the updater, the controller OS, a boot-ROM verifier, or the printer's network update route.

There is a **second, conditional gate** in the first IPL. Its signature-header parser at raw code offset `0xa1b8` reads the declared length. After a valid first record, `0x26898` sets the shared stream state at `0x46339012` to `2` **only if** a byte at `0x82c00000` equals `2`; otherwise it sets state `3`. The finalizer at `0x9614` checks the remaining-byte counter at `0x46339014` and calls the P-256 decision routine at `0xa2a0` only in state `2`. In that state, a positive count enters error status `2`, so the length candidate would be rejected if a LAN update traverses this first-IPL path in mode `2`. The live value of `0x82c00000`, the order and reachability of the first IPL and decoded controller paths, and the host updater's validation remain unknown.

The finalizer is not dead code: [the first-IPL dispatch checker](../scripts/inspect_ipl0_update_dispatch.py) maps the startup copy `0x8010 -> 0x46309000` and recovers the update callback table at RAM `0x463297ac` from IPL offset `0x287bc`. Its `+0x0c` entry resolves to the finalizer at IPL offset `0x9614`. The early boot code calls mode selector `0xd58` at `0xb18`; a zero result skips the update trampoline, while a nonzero result branches through `0x3108` to `0x85ec`, then `0x8f60`. That routine invokes the finalizer slot when its status byte is not `5`. The stock `XB` marker can cause the mode selector to return zero under its preceding boot-source conditions. This establishes a conditional boot route to the gate, but does not establish whether a ROM1 transfer enters that route or the live status and mode values.

The first IPL itself writes that mode byte during early startup in `0xd58`. It selects `0` or `1` from boot-source checks, and reaches its mode-`2` assignment after those checks pass and either a separate status condition succeeds or the two-byte family marker fails to match its built-in `XB` marker. The comparison source pointer at `0xe84` is `0x74fff8`, which points to `XB22Q5` at the end of the extracted first IPL; its built-in marker at `0xe88` is `XB`. The stock image therefore passes this *one* family comparison. This does not establish the other boot conditions or the live mode. The later initialization at `0x8f60` reads the same `0x82c00000` byte, and the first-IPL update handler at `0x25ec8` uses it to restrict `fv` firmware commands. [`inspect_ipl0_boot_mode.py`](../scripts/inspect_ipl0_boot_mode.py) checks these pointers and marker bytes from a separately supplied, hash-checked first IPL.

The corrected [controller CROM trace](controller-crom-trace.md) now maps the Linux first-stage `GetRequestID` request through ROM1 selection, a recovered RAM callback table, a channel-1 body read, and the package receiver that calls this signed reader. This is static code evidence and isolated emulation, not a captured live accepted transfer. The physical printer is accessible only over Wi-Fi and has no established recovery channel, so no 40 MB candidate upload has been attempted. The live controller reply and any earlier authentication gate still need resolution before claiming an install or device impact.

The reader's success also has a mapped completion route: ROM1 status record `0xca4` becomes `1`, and the controller hands three staged-record descriptors to another component using commands `0x2a` and `0x2b`. The receiving code at `0x4370d47c`/`0x4370d588` is outside the decoded controller segment. Its validation and flash behavior remain unproved, so the reader's success cannot be equated with installation.

### Offline two-stage control

The optional `--patch-ipl-finalizer` switch in [`build_length_gate_candidate.py`](../scripts/build_length_gate_candidate.py) changes one ARM instruction in the candidate's first IPL at raw code offset `0x97d0`: `BNE 0x97f4` becomes `BNE 0x97fc`. With a positive remaining count, this jumps past the first IPL's local error call. It leaves the running printer's IPL untouched. The builder recalculates the first record's sum and SHA-1 digest along with the Wi-Fi record's checks.

An offline candidate combining the patched Wi-Fi SquashFS, the one-byte unsigned length increase, one trailing byte, and this four-byte first-IPL patch has SHA-256 `e0f51dd21a61bb0f6162810378a84b3bd4085c6d3f49787d273aab620e8f1986`. All six record sums and three SHA-1 digests match. The [controller ARM reader emulator](../scripts/emulate_controller_reader_length.py) returns `1` with one byte remaining and zero ECDSA calls. The [first-IPL branch emulator](../scripts/emulate_ipl0_finalizer_branch.py) reaches the error routine once for the original instruction and zero times for the patched instruction, with the same positive count. This only tests isolated code paths. The candidate's original ECDSA signature remains invalid against the running IPL key; boot-ROM authentication, staging of the changed IPL, live mode, and physical installation remain unknown. The candidate binary remains outside this repository and has not been uploaded.

The [ET-3850 series recovery instructions](https://download4.epson.biz/sec_pubs/et-3850_series/useg/en/GUID-E83E8F59-3D8B-4EC3-86D0-7FC5B6BB1076.htm) specify USB for a failed firmware update and say network recovery is unavailable. A USB cable is now connected, but recovery transport and acceptance remain unverified. This offline result is not enough to justify a physical flash before the remaining trust and commit behavior is resolved.
