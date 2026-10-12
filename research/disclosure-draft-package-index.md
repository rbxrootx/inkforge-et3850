# Draft: XB22Q5 controller package parser writes beyond image tables

**Status:** Research draft for vendor triage. The memory write is reproduced offline in extracted ARM code. Network reachability and physical impact are not yet demonstrated.

## Affected build

Epson ET-3850, firmware status `05.15.XB22Q5`. The analyzed RCX has SHA-256 `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675`. The relevant decoded controller segment has SHA-256 `7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416`. The live unit reports the same version, but the segment was extracted from a package rather than dumped from the unit.

## Observation

At mapped address `0x457779e0`, the `EPSON IPLJ6XB` header parser reads the second descriptor's ID at header offset `0x38`, scans 37 entries for a duplicate, and writes to two tables indexed by that ID. It does not reject ID `0x25` or higher before writing. The normal range is `0` through `0x24`. With ID `0x25`, the first write starts at `0x45c65d6c`, past the first table; the second starts at `0x45d660e4`, past the second table and at the destination buffer for the controller's copied ECDSA public key. The key-copy routine at `0x45778e40` obtains its source from `0x4fb26800`; the later verifier uses the copied key buffer. Header fields control 20 of the 24 bytes written in a slice; the parser writes its header pointer into the other four bytes.

The package reader at `0x45778404` reads the first 4096-byte payload header and calls this parser before its signed-stream routine at `0x45778264` has hashed the declared 40,603,648-byte payload and checked ECDSA. Modifying one descriptor byte makes the RCX signature fail against the existing IPL key, while isolated execution of the parser still performs the out-of-range writes. This is a parser-order and bounds-check issue in the decoded update path, not proof that the network update interface reaches it.

## Offline reproduction

Run [`emulate_controller_header_index.py`](../scripts/emulate_controller_header_index.py) with the separately obtained RCX and its decoded controller segment. The script checks both SHA-256 hashes, invokes the actual ARM parser in Unicorn, and reports these controls:

| Descriptor ID | Parser result | Write beyond 37-entry tables | Copied-key buffer overlap |
| --- | ---: | --- | --- |
| `0x24` | 1 | No | No |
| `0x25` | 1 | Yes | Yes |
| `0xfe` | 1 | Yes | No |
| `0xff` | 0 | No | No |

No printer packet, modified firmware image, administrator credential, serial number, or proprietary binary is included in this repository.

## Questions for confirmation

1. Does a production update input on ET-3850 reach `0x45778404` / `0x457779e0` with attacker-controlled package bytes?
2. Does the physical XB22Q5 controller use the extracted table and key-buffer layout?
3. Can the write affect integrity, availability, or the signature decision on the device? No valid substitute key or successful modified flash has been shown.

## Suggested fix

Reject descriptor IDs outside the 37-entry range before any indexed read or write. Authenticate the complete signed package before parsing or copying untrusted descriptor fields into controller state. If streaming is required, keep parser and verifier state isolated until the signature succeeds.
