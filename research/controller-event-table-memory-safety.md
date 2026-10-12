# Retracted controller event-table lead

**Status: disproved.** An earlier isolated ARM run appeared to make group `0x76` subcommands 7–9 write near address zero. The decoded CROM segment had been mapped at provisional address `0x45670000`, but its embedded absolute pointers show that it loads at `0x4566ff74`. The 0x8c error caused the emulator to execute jump-table bytes as instructions.

With the correct load address, the [hash-checked table inspector](../scripts/inspect_update_event_dispatch.py) and [isolated ARM dispatcher](../scripts/emulate_update_event_dispatch.py) select valid handlers for subcommands 6, 7, 8, and 9. Subcommand 8 selects runtime address `0x45809a2c`, corresponding to Ghidra's provisional `0x45809ab8`, and enters the ROM1/ROM2 selector block. No low-address write occurs in this corrected dispatch test.

The earlier low-address-write claim should not be reported as a vulnerability. The corrected mapping also resolves the separate group `0x0b`, `0x77`, and `0x8d` event-table anomalies. See the [controller CROM trace](controller-crom-trace.md) for the current update-path analysis.
