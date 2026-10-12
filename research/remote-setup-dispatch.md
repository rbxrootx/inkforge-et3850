# Remote `||` dispatch and the setup buffer

The XB22Q5 controller's two-letter remote command table contains both `st`
(handler `0x459aef04`) and `||` (handler `0x459b0a4c`). The `st` status command
has already responded over the printer's public SNMP private OID. On
2026-10-12, a deliberately invalid `||` request also returned a command-specific
reply from the live ET-3850 at `192.168.0.12`. This establishes that the outer
`||` dispatcher is reachable over that SNMP tunnel. It does **not** establish
that a setup archive can be written or restored.

## Static command chain

The `||` handler checks a `J6` header. Its third byte selects an inner command;
the fourth must complement it, and a one-bit rotation of the fifth must equal
it. The same handler has a state gate: when its third call argument is `4`, a
controller state word at `0x43edb930` must be `1`. The value of that word on the
live device and the exact meaning of the argument have not been established.

The inner table has `p` at `0x45b7c408` (handler `0x459b14e8`) and `q` at
`0x45b7c410` (handler `0x459b1678`). The `p` handler expects a seven-byte inner
header: a type, a little-endian 32-bit offset, and a little-endian 16-bit body
length. It requires the supplied length to match the header and caps it at
`0x8000`. Type `2` copies bytes into a fixed `0x7fe0`-byte controller buffer.
Type `3` requires 32-byte blocks, a sequential offset, and one of two controller
mode checks to return `1`; it forwards each block through queue `0x78` event
`0x302` and caps the running offset at `0x50000`. The `q` handler includes a
type-`3` 64-byte block path through event `0x301` under similar mode checks.

Queue `0x78` event `0x302` calls `0x458c3eb0`, which selects the write mode;
event `0x301` calls `0x458c3f64`, which selects the read mode. Event `0x303`
calls `0x458c3e28`, whose successful callback can post command `2`
(`readsetup`) or `3` (`writesetup`) to queue `0x6e` event `7`. Linux `nwsoc`
then receives the internal setup command, as traced in
[setup-command-event-chain.md](setup-command-event-chain.md).

This is a plausible transport to the [Linux restore parser](setup-restore-parser.md).
Its live authorization and state transitions have not been demonstrated, so it
is not yet an installation route or a confirmed remotely exploitable file write.

## Live, no-change probe

The [probe](../scripts/probe_remote_setup_dispatch.py) constructs SNMP GET OIDs
under `1.3.6.1.4.1.1248.1.2.2.44.1.1.2.1`, using `public`, a two-letter command,
a little-endian body length, and body bytes. It sent three cases:

| Case | Reply bytes | Interpretation |
| --- | --- | --- |
| Unknown `zz`, invalid `J6` | `00 7a 7a 3a 3b 0c` | Generic `zz:;` reply. |
| `||`, invalid `J6` checksum | `00 7c 7c 3a 30 30 3a 4e 41 3b 0c` | Command-specific `||:00:NA;` rejection. |
| `||`, valid `J6` with `p` type `2` and zero data bytes | `00 7c 7c 3a 37 30 3a 4e 41 3b 0c` | `||:70:NA;` rejection. No bytes were supplied for copying. |

These responses show dispatch and rejection. The `NA` on the zero-byte case may
come from the outer state gate or a later length check; the probe alone does
not identify which. No setup archive, firmware bytes, or filename was sent.

Run `python scripts/inspect_setup_event7.py <decoded-controller-segment0>` to
check the static tables against the hash-locked image. Run
`python scripts/probe_remote_setup_dispatch.py <printer-ip>` to repeat only the
invalid-envelope cases; add `--zero-copy` to repeat the no-change inner case.
The next necessary proof is the state-gate meaning and a harmless accepted
setup transaction before attempting any restore archive.
