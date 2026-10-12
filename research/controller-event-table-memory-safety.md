# Controller event table: offline invalid-write lead

This is an isolated execution result for the decoded XB22Q5 CROM segment 0
(SHA-256 `7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416`).
It is **not** a demonstrated ET-3850 network vulnerability or an installation
route. No event was sent to the printer.

The group `0x76` receiver reads the event's 16-bit subcommand at offset `+8`,
compares it with 14, then executes `ldrlo pc, [pc, r0, lsl #2]` at
`0x45809a10`. Entries 7, 8, and 9 in the decoded table point into the table
itself. The table words decode as conditional ARM `strmi` instructions. The
preceding comparison leaves the negative flag set for these three indices,
so executing a table word attempts a write near virtual address zero.

[`emulate_update_event_dispatch.py`](../scripts/emulate_update_event_dispatch.py)
runs only the actual dispatch instructions from the hash-locked CROM in
Unicorn. With a synthetic event and a sentinel value in R9, it observes:

| Subcommand | Isolated outcome |
| --- | --- |
| 6 | Returns to the event loop |
| 7 | Unmapped 4-byte write to `0x9eb` |
| 8 | Unmapped 4-byte write to `0xa0c` |
| 9 | Unmapped 4-byte write to `0xa69` |

The decoded `Method:`/`URI:` parser has a POST branch that queues subcommand
8, but no caller for that parser or LAN route to this receiver has been
identified. The physical controller's low memory mapping and live jump table
are also unknown. On real hardware, the same instruction might fault, write
to mapped memory, or be bypassed by a runtime table change. A report needs a
non-destructive reachability proof and a live observation before claiming
denial of service or memory corruption on the printer.
