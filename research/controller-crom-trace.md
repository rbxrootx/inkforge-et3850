# XB22Q5 controller CROM trace

This is an offline trace of an image inside the separately obtained ET-3850 XB22Q5 RCX. It does not establish a LAN exploit or an installation method. No controller payload was sent to the printer.

## Reproduce the extraction

The RCX with SHA-256 `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675` contains a `CROM` region at absolute RCX offset `0x167112`, inside its first IPL. The independent [abrasive/epson-reversing CROM decoder](https://github.com/abrasive/epson-reversing) expands this region into two segments. Run [the hash-checked extractor](../scripts/extract_controller_crom.py) with your own RCX and a separately obtained `uncrom.py`:

```powershell
python scripts/extract_controller_crom.py --rcx path/to/FWCJ61TL.rcx --uncrom path/to/uncrom.py --output-dir path/to/decoded
```

Segment 0 is 5,686,304 bytes, SHA-256 `7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416`. Segment 1 is 3,036 bytes, SHA-256 `5c6af9a703999265215faeb814cb1e06cf38bbcfef8d78b703bcd031962caeb9`. ARM branch targets and many data pointers in segment 0 resolve when it is mapped at `0x45670000`; the request table described below contains exceptions. All addresses below use that mapping. The decoded bytes include `EpsonLocalReq`, `ReadSetup`, `WriteSetup`, `SetupData:`, and `IPPRes:` strings.

An [all-region inventory](../scripts/inventory_crom_regions.py) finds five CROM headers in this RCX: `0x144112`, `0x167112`, `0x69f112`, `0x757122`, and `0x16da122`. They decode into eight segments in total. Of those decoded byte streams, only the `0x167112` segment 0 contains the exact ASCII strings `GetRequestID`, `/DOWN/FIRMWAREUPDATE/`, `EpsonLocalReq`, `Method:`, and `URI:`. This does not rule out encoded names or runtime-generated handlers in the other images, but it focuses the literal-string search on this segment.

The separate C implementation of the same public CROM decoder was also run against the `0x167112` stream, trimmed immediately before its `0xff` padding. Its two output SHA-256 hashes exactly matched the Python decoder's segment hashes above. The odd request-table words below are therefore not a difference between those two decoder implementations; runtime relocation or inactive code remains possible.

## `SetupData:` control path

- `0x4591465c` reads a pointer from event offset `+0x0c`, checks that its first 32 bytes are in the base64 alphabet, and then calls `0x4589b0fc`. The event dispatcher at `0x45914f78` routes group `0x6e`, subcommand `0x1a` to this function through jump-table entry 26.
- `0x4589b0fc` builds `SetupData:` followed by those 32 bytes. It calls internal request function `0x45898378` and compares the reply prefix to `HR:200`. This proves an internal message format, not that a LAN client can send it.
- The request function enqueues group `0x0b`, subcommand `0x42` through `0x4589c784`. In this decoded image, the group `0x0b` dispatcher at `0x45833f0c` has jump-table entries `0x41` and `0x42` pointing directly to branches back to its wait loop at `0x45833f18`; they do not enter the adjacent handler calls. The [event-table checker](../scripts/inspect_controller_event_routes.py) reproduces those targets from the segment bytes. This is a static observation of this image, not a live dump or proof that runtime patching is impossible.
- A separate routine at `0x4591130c` checks for a `SetupData:` prefix in an incoming buffer and copies data after that prefix into controller state. Direct ARM calls and 32-bit function-pointer references to this routine were not found in the decoded segment; its registration and transport remain unresolved.
- `0x4589be1c` and `0x4589be54` enqueue group `0x6e`, subcommand `0x1a`. The only direct ARM callers found in this decoded segment are `0x457eb118` and `0x457eb1ac`, respectively. An indirect caller or another image could exist.
- Both callers build a buffer using `0x457e9330`, which writes the `IPPRes:` prefix, a three-digit status, and CRLF before appending payload bytes. `0x457eb118` is directly called by `0x45947da8`, a routine that serializes configuration fields into an IPP response-shaped buffer. The latter is reached from a group `0xb0` dispatcher at `0x4593b968`.

The observed `IPPRes:` producer and base64-only consumer do not fit: the prefix contains `:`, which fails the consumer's first-32-byte check. This may be an unused path, a build-time mismatch, or an analysis gap. It is **not** a demonstrated way to send setup data from the LAN. The exact role of the `SetupData:` request and its internal peer remains open.

## Internal `Method:` / `URI:` parser

The isolated Linux [HTTP rehost](application-rehost.md) now shows a generic `/DOWN/` POST sending `EpsonLocalReq:GetRequestID` with the full firmware-update URI. With a fabricated `HR:200` reply, a 19-byte marker reached the Linux EPIDC send interface. The decoded controller segment contains `GetRequestID` at file offset `0x55e1f1` (mapped `0x45bce1f1`). Ghidra found no direct reference to that exact string, and a raw search found no exact 32-bit pointer to its start. A nearby table does contain `0x45bce1f9`, pointing eight bytes into the name at its suffix `stID`; that is not a full-name reference.

The [hash-checked request-table checker](../scripts/inspect_controller_request_table.py) follows a literal loaded by the generic prefix matcher at `0x4590e170`: `0x4590e67c` holds `0x45ae9f78`. At that table address, the first word is `0x459133f0`, which points into code/data rather than to the apparent string pool; advancing four bytes would make the alternating words look more like string/handler pairs, but many string pointers then land inside names, including the `stID` suffix above. The same table holds an exact pointer to `/FIRMWAREUPDATE` at `0x45ae9fe4`. At raw record 4, the apparent prefix begins with a NUL; if this table were used unchanged on nonempty input, the prefix matcher would select a pointer into ASCII data as a callback. That inconsistency is evidence that the decoded table cannot be taken as live dispatch state. We have not shown whether it is dead, transformed in RAM, or unrelated to the live `GetRequestID` request. Its anomalous words do not establish a device vulnerability or a working controller approval path.

A separate ARM routine beginning at `0x45912740` parses records with inline `Method:` and `URI:` labels. It recognizes `POST`, `GET`, and `HEAD`, strips a query suffix from the URI, and dispatches to route handlers. One path queues controller event group `0x76`, subcommand `8`, for a POST URI prefix. This is structurally consistent with a Linux-to-controller request relay, but the prefix's runtime value and the event's ultimate handler have not been established. Neither a direct ARM branch nor an exact 32-bit pointer to `0x45912740` was found in the decoded segment. Its presence therefore does not prove the live HTTP firmware upload reaches it.

The decoded controller's group `0x76` receive loop at `0x458099ec` reads a subcommand, compares it with `14`, and indexes a PC-relative ARM jump table at `0x45809a18`. [A hash-checked table inspection](../scripts/inspect_update_event_dispatch.py) shows that subcommand `8` selects `0x45809a2c`, an address **inside the table itself**, not the adjacent `ROM1`/`ROM2` handler at `0x45809ab8`. Entries `7` and `9` likewise point inside the table. This makes the parser-to-`ROM1` handler hypothesis weaker for this static image. It does not establish the behavior of a live controller that might patch the table in RAM, and no incoming network path to this parser has been proved.

The nearby decoded data contains `/DOWN/FIRMWAREUPDATE/`, but no direct 32-bit pointer to its first character was found. The `Method:` / `URI:` parser and that path string cannot be joined solely by their proximity in this image. An active caller, route-table selection, and signature decision remain necessary before testing a modified RCX on the printer.

An [isolated execution of this dispatcher](controller-event-table-memory-safety.md)
shows that subcommands 7, 8, and 9 execute table bytes as conditional stores
to low virtual addresses (`0x9eb`, `0xa0c`, and `0xa69` with the supplied event).
This is a memory-safety lead in the decoded image. The event's LAN
reachability and the live controller's memory mapping are still unknown.

The additional `0x0b` dispatch finding gives another reason not to treat the `SetupData:` request as a working update channel in this build: its queued command currently selects a loop-back entry. The image also contains `/DOWN/FIRMWAREUPDATE/` and `EpsonLocalReq:CancelDOWNCONTENT` strings, but neither string alone links the Linux HTTP relay to a flash writer or a signature decision. The `/DOWN/FIRMWAREUPDATE/` bytes start at `0x45ae594f`; no exact 32-bit pointer to that address was found in this segment. A nearby literal used by `0x4590d4d4` points to the preceding NUL byte at `0x45ae594e`. Its callee `0x458aefc8` computes the string length from that pointer and copies zero bytes, so this routine does not use the path even indirectly through a `+1` adjustment.

The [isolated ARM emulation](../scripts/emulate_setup_gate.py) runs the actual `0x4591465c` instructions from the hash-checked controller segment. It stops before the internal request call. An `IPPRes:200` prefix and 31 base64 characters both return before that call; 32 base64 characters reach it. This verifies the input gate, but it does not emulate the controller OS or prove any network entry point.

A separate ARM routine at `0x458089a4` compares a supplied name with inline `ROM1` and `ROM2` strings, checks controller state, and queues an event for either name. Its direct call at `0x45809ac8` sits in a larger group `0x76` dispatcher. The recovered 14-entry jump table at `0x45809a18` does not point to that call block, and no direct ARM branch or exact pointer to the block was found in this segment. This prevents treating that routine as the live `/DOWN/FIRMWAREUPDATE/ROM1` handler. The `CancelDOWNCONTENT` routine at `0x45898d4c` builds an `EpsonLocalReq:` request through the same internal-request function used by `SetupData:`; it does not show how a network upload is validated.

## `ReadSetup` and `WriteSetup` strings

A controller property metadata entry at segment-0 file offset `0x47a854` names `ReadSetup` and has ID `0x1443`. `WriteSetup` is also present as a string, but its exact address has no direct 32-bit pointer in this image. Neither observation identifies a network endpoint or a caller that accepts an arbitrary restore archive. The Linux-side [setup restore parser](setup-restore-parser.md) therefore remains a static file-write lead with no proved LAN source.

## Controller-side `EPSONSIGN` gate

Another path in this decoded controller segment processes an `EPSONSIGNXB20d` package. At `0x45778e40`, it checks the header family and payload length, copies the 64-byte signature from header offset `+0x20` into controller state, and copies a 64-byte public key from **RAM address `0x4fb26800`** into adjacent state. The first IPL's startup descriptor at raw offset `0x5628c` copies 4096 bytes from its own offset `0x13f000` to that same RAM address. The copied first 64 bytes have SHA-256 `895d41e09d140db0529123757cba7e9ea24aea1ea6864e54a1a5d565ee6b1cac`, matching the original RCX key. The [hash-checked key-source checker](../scripts/inspect_controller_signature_gate.py) reproduces the constants and copy relationship from separately extracted files.

The parser is called by the streaming routine at `0x45778264`. That routine hashes the payload and, when all expected bytes have arrived, calls `0x45778f0c`, which passes the copied key, signature, and 32-byte digest to `0x45768cd4` / `0x45768d04`. The latter constructs an elliptic-curve key with curve ID `0x19f` and feeds the signature components and digest to its verification routine. The wrapper at `0x45768cd4` compares the crypto result with **exactly `1`** and changes every other value to `0`; an error return is not treated as success. The package reader at `0x45778404` uses this streaming routine. One caller at `0x45778a88` selects it for command `0xb10`; a separate receiver at `0x45777488` also selects it for modes `0xb` and `0x11`. The receiver reads through a callback installed from an event record at `0x45777638`; the event's producer remains unidentified. There is no demonstrated link from the printer's HTTP `/DOWN/` relay to this controller package path.

For this path, simply replacing the public key **inside the candidate RCX** cannot change the key already copied from the running IPL into `0x4fb26800`. The decoded controller segment has one direct 32-bit literal naming that RAM address, at this parser's key-copy site. This does not exclude indirect writes or another image changing it. The [existing offline signature check](../scripts/check_rcx_against_current_ipl.py) accepts the original XB22Q5 RCX against that IPL key and rejects the self-signed Wi-Fi candidate. This is a concrete rejection reason for this decoded controller path, not a proof that every possible update route uses it or that the live device has identical RAM state. No key-changing write path or alternative acceptance rule has been established.

Reproduce the static key-source check with `python scripts/inspect_controller_signature_gate.py path/to/decoded-controller-0.bin path/to/ipl0-code.bin`. Neither input is distributed here.

A [second decoded controller image](secondary-update-mode.md) contains a lower-level ROM programmer and a `Program Update Mode` completion display. That routine checks a byte sum after programming but has no established network caller. Its existence does not bypass this signature path.

## Next proof needed

Find the producer of the `WRITESETUP` chunks consumed by Linux `nwsoc`, then trace that producer to an authenticated or unauthenticated LAN handler. A harmless chosen-filename write on the test printer would be needed before calling this a vulnerability. The controller CROM trace alone does not justify sending a modified firmware image.
