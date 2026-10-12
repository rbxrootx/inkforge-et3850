# ET-3850 setup restore parser

This is a **static research lead**, not a demonstrated network exploit. The code is in the `nwsoc` program extracted from the XB22Q5 ET-3850 recovery image (SHA-256 `70728f452c5358c4ef04ec39354c4656e662af675ce88d161f05949ac0`). Ghidra addresses below are virtual addresses; the corresponding binary file offsets are `address - 0x10000`.

## Data flow found in the program

1. The restore service initializer at `0x2158b0` registers controller event callbacks for `READSETUP` (`0x1b`) and `WRITESETUP` (`0x1c`). The latter points at `0x2151b8`.
2. `0x2151b8` buffers fixed-size data pieces from the controller and calls archive validator `0x216248` once the declared length is collected.
3. `0x216248` checks a model/version header, a CRC32 computed by `0x21687c`, and length-prefixed record boundaries. In the inspected branch it does not compare each filename to an allowlist. CRC32 detects accidental corruption but does not authenticate the source.
4. Following a successful restore-start result, `0x215100` calls archive writer `0x2166fc`. That writer takes a length-prefixed filename directly from each archive record, calls `open(filename, flags)`, and writes the accompanying bytes.

The writer has two branches controlled by a controller-provided mode. Their literal open flags are `0x241` (`O_WRONLY | O_CREAT | O_TRUNC`) and `0x201` (`O_WRONLY | O_TRUNC`). The latter can overwrite an existing file; the former can also create one if the containing directory is writable. The archive writer itself has no path prefix or allowlist check in the inspected code. The backup generator at `0x215c30` draws filenames from a fixed configuration/certificate list, but the restore validator and writer do not compare incoming filenames to that backup list.

## What remains unproved

- Whether any LAN API can cause the printer controller to send attacker-chosen `WRITESETUP` pieces to this Linux callback. The observed event path originates at the controller interface. The `ReadSetup` and `WriteSetup` strings near `0xea974` are used in an internal local-request mapping, and `EpsonLocalReq:WriteSetup` at `0xea2dc` is framed for the controller channel; neither establishes a reachable HTTP or SNMP endpoint.
- Which controller mode this particular live device uses, whether the controller accepts a modified archive, and what authorization applies before it forwards restore pieces.
- Whether the candidate Wi-Fi change can be installed through this route. The `/opt/nwsoc_data/ExtBoot` boot hook is a potential target only if the create-capable branch is active and a network-supplied archive reaches the parser. No such archive has been sent to the printer.

This finding should not be reported as remote code execution yet. A defensible report needs a network entry point, a reversible proof of a chosen filename write, and confirmation of the affected firmware version. No device credentials or printer identifiers are needed in a public write-up.

## SNMP cross-check

A read-only SNMPv2c query to the live printer returned a normal `sysDescr` under `public`. The claimed `internal` community from an older-model third-party reset script received no response. A vendor OID shaped like that script's EEPROM read command returned an eight-byte value under `public`, but the value was identical for seven adjacent addresses and an out-of-range address. That is **not** evidence of address-specific EEPROM access on this ET-3850. No SNMP SET was sent and no returned bytes were saved.
