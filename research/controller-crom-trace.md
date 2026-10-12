# XB22Q5 controller CROM trace

This is an offline trace of an image inside the separately obtained ET-3850 XB22Q5 RCX. It does not establish a LAN exploit or an installation method. No controller payload was sent to the printer.

## Reproduce the extraction

The RCX with SHA-256 `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675` contains a `CROM` region at absolute RCX offset `0x167112`, inside its first IPL. The independent [abrasive/epson-reversing CROM decoder](https://github.com/abrasive/epson-reversing) expands this region into two segments. Run [the hash-checked extractor](../scripts/extract_controller_crom.py) with your own RCX and a separately obtained `uncrom.py`:

```powershell
python scripts/extract_controller_crom.py --rcx path/to/FWCJ61TL.rcx --uncrom path/to/uncrom.py --output-dir path/to/decoded
```

Segment 0 is 5,686,304 bytes, SHA-256 `7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416`. Segment 1 is 3,036 bytes, SHA-256 `5c6af9a703999265215faeb814cb1e06cf38bbcfef8d78b703bcd031962caeb9`. ARM branch targets and data pointers in segment 0 resolve when it is mapped at `0x45670000`. All addresses below use that mapping. The decoded bytes include `EpsonLocalReq`, `ReadSetup`, `WriteSetup`, `SetupData:`, and `IPPRes:` strings.

## `SetupData:` control path

- `0x4591465c` reads a pointer from event offset `+0x0c`, checks that its first 32 bytes are in the base64 alphabet, and then calls `0x4589b0fc`. The event dispatcher at `0x45914f78` routes group `0x6e`, subcommand `0x1a` to this function through jump-table entry 26.
- `0x4589b0fc` builds `SetupData:` followed by those 32 bytes. It calls internal request function `0x45898378` and compares the reply prefix to `HR:200`. This proves an internal message format, not that a LAN client can send it.
- The request function enqueues group `0x0b`, subcommand `0x42` through `0x4589c784`. In this decoded image, the group `0x0b` dispatcher at `0x45833f0c` has jump-table entries `0x41` and `0x42` pointing directly to branches back to its wait loop at `0x45833f18`; they do not enter the adjacent handler calls. The [event-table checker](../scripts/inspect_controller_event_routes.py) reproduces those targets from the segment bytes. This is a static observation of this image, not a live dump or proof that runtime patching is impossible.
- A separate routine at `0x4591130c` checks for a `SetupData:` prefix in an incoming buffer and copies data after that prefix into controller state. Direct ARM calls and 32-bit function-pointer references to this routine were not found in the decoded segment; its registration and transport remain unresolved.
- `0x4589be1c` and `0x4589be54` enqueue group `0x6e`, subcommand `0x1a`. The only direct ARM callers found in this decoded segment are `0x457eb118` and `0x457eb1ac`, respectively. An indirect caller or another image could exist.
- Both callers build a buffer using `0x457e9330`, which writes the `IPPRes:` prefix, a three-digit status, and CRLF before appending payload bytes. `0x457eb118` is directly called by `0x45947da8`, a routine that serializes configuration fields into an IPP response-shaped buffer. The latter is reached from a group `0xb0` dispatcher at `0x4593b968`.

The observed `IPPRes:` producer and base64-only consumer do not fit: the prefix contains `:`, which fails the consumer's first-32-byte check. This may be an unused path, a build-time mismatch, or an analysis gap. It is **not** a demonstrated way to send setup data from the LAN. The exact role of the `SetupData:` request and its internal peer remains open.

## Internal `Method:` / `URI:` parser

A separate ARM routine beginning at `0x45912740` parses records with inline `Method:` and `URI:` labels. It recognizes `POST`, `GET`, and `HEAD`, strips a query suffix from the URI, and dispatches to route handlers. One path queues controller event group `0x76`, subcommand `8`, for a POST URI prefix. This is structurally consistent with a Linux-to-controller request relay, but the prefix's runtime value and the event's ultimate handler have not been established. Neither a direct ARM branch nor an exact 32-bit pointer to `0x45912740` was found in the decoded segment. Its presence therefore does not prove the live HTTP firmware upload reaches it.

The decoded controller's group `0x76` receive loop at `0x458099ec` reads a subcommand, compares it with `14`, and indexes a PC-relative ARM jump table at `0x45809a18`. [A hash-checked table inspection](../scripts/inspect_update_event_dispatch.py) shows that subcommand `8` selects `0x45809a2c`, an address **inside the table itself**, not the adjacent `ROM1`/`ROM2` handler at `0x45809ab8`. Entries `7` and `9` likewise point inside the table. This makes the parser-to-`ROM1` handler hypothesis weaker for this static image. It does not establish the behavior of a live controller that might patch the table in RAM, and no incoming network path to this parser has been proved.

The nearby decoded data contains `/DOWN/FIRMWAREUPDATE/`, but no direct 32-bit pointer to its first character was found. The `Method:` / `URI:` parser and that path string cannot be joined solely by their proximity in this image. An active caller, route-table selection, and signature decision remain necessary before testing a modified RCX on the printer.

The additional `0x0b` dispatch finding gives another reason not to treat the `SetupData:` request as a working update channel in this build: its queued command currently selects a loop-back entry. The image also contains `/DOWN/FIRMWAREUPDATE/` and `EpsonLocalReq:CancelDOWNCONTENT` strings, but neither string alone links the Linux HTTP relay to a flash writer or a signature decision. The `/DOWN/FIRMWAREUPDATE/` bytes start at `0x45ae594f`; no exact 32-bit pointer to that address was found in this segment. A nearby literal used by `0x4590d4d4` points to the preceding NUL byte at `0x45ae594e`, so that routine does not establish use of the path.

The [isolated ARM emulation](../scripts/emulate_setup_gate.py) runs the actual `0x4591465c` instructions from the hash-checked controller segment. It stops before the internal request call. An `IPPRes:200` prefix and 31 base64 characters both return before that call; 32 base64 characters reach it. This verifies the input gate, but it does not emulate the controller OS or prove any network entry point.

A separate ARM routine at `0x458089a4` compares a supplied name with inline `ROM1` and `ROM2` strings, checks controller state, and queues an event for either name. Its direct call at `0x45809ac8` sits in a larger group `0x76` dispatcher. The recovered 14-entry jump table at `0x45809a18` does not point to that call block, and no direct ARM branch or exact pointer to the block was found in this segment. This prevents treating that routine as the live `/DOWN/FIRMWAREUPDATE/ROM1` handler. The `CancelDOWNCONTENT` routine at `0x45898d4c` builds an `EpsonLocalReq:` request through the same internal-request function used by `SetupData:`; it does not show how a network upload is validated.

## `ReadSetup` and `WriteSetup` strings

A controller property metadata entry at segment-0 file offset `0x47a854` names `ReadSetup` and has ID `0x1443`. `WriteSetup` is also present as a string, but its exact address has no direct 32-bit pointer in this image. Neither observation identifies a network endpoint or a caller that accepts an arbitrary restore archive. The Linux-side [setup restore parser](setup-restore-parser.md) therefore remains a static file-write lead with no proved LAN source.

## Next proof needed

Find the producer of the `WRITESETUP` chunks consumed by Linux `nwsoc`, then trace that producer to an authenticated or unauthenticated LAN handler. A harmless chosen-filename write on the test printer would be needed before calling this a vulnerability. The controller CROM trace alone does not justify sending a modified firmware image.
