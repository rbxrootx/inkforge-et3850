# ET-3850 setup command event chain

The XB22Q5 controller can ask Linux `nwsoc` to run `readsetup` or `writesetup`. This is an **internal controller-to-Linux path**. It does not establish a LAN upload or a way to install a Wi-Fi change.

The decoded controller CROM segment 0 has SHA-256 `7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416` and load base `0x4566ff74`. The [hash-checked inspector](../scripts/inspect_setup_event7.py) reproduces the two command IDs and event dispatch target.

## Recovered chain

1. Controller function `0x45899ae8` allocates an event addressed to queue `0x6e`. It writes event number `7` at offset `+8`, the requested command number at `+0xc`, and an opaque callback value at `+0x10`. Its thunk is at `0x45895440`.
2. The queue consumer at `0x45914eec` waits on queue `0x6e`. Its event-7 case calls `0x45914970`.
3. `0x45914970` checks a controller mode byte for value `3`, then passes the event's command byte to `0x4589aac4`.
4. `0x4589aac4` looks up command `2` as `readsetup` or command `3` as `writesetup` in the table at `0x45ae5b04`, formats an internal request, and sends it through controller channel command `0x15`. For these two commands it also writes value `8` to internal setting `0x30e`.
5. Linux `nwsoc` function `0x184858` compares the received command string to the same names and maps them to command IDs `2` and `3`. It starts an asynchronous worker through `0xa44e0`. This callback was registered during `nwsoc` startup by `0x1835f8`.

One controller producer at `0x458c3e28` posts command `2` or `3` when its callback receives result `1`, according to a mode byte: `0` chooses `readsetup`, `1` chooses `writesetup`. The mode is set in `0x458c3f64` and `0x458c3eb0`, respectively. Its immediate caller is in an event dispatcher near `0x458c75b8`. The external source and authorization for that dispatcher have not been traced.

On the live printer, read-only HTTP GETs to `/readsetup`, `/writesetup`, `/UP/readsetup`, and `/UP/writesetup` all returned `404` on 2026-10-12. This only rules out those four direct paths; it does not prove there is no other network producer.

## Why this matters

The [Linux restore archive parser](setup-restore-parser.md) accepts record filenames without an allowlist and later opens them with truncate flags. If a network input can supply chosen restore records to this chain, a persistent file change such as the existing `ExtBoot` boot hook may be possible without a modified RCX. That condition remains unproved. No restore archive was sent to the printer, no file was written, and no Wi-Fi change was installed.

Next, trace the producer of controller event `7` back through its caller near `0x458c75b8` and establish a LAN request, its authorization requirements, and a reversible read-only or harmless-file test. Until then, the arbitrary-filename behavior is a research lead rather than a confirmed remotely exploitable vulnerability.
