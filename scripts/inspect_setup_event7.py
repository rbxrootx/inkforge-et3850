#!/usr/bin/env python3
"""Check XB22Q5 setup events and the remote command dispatch tables."""

import argparse
import hashlib
from pathlib import Path
import struct

EXPECTED_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
IPL0_SHA256 = "bf046b5bd5f5499c377bcbcb7b27aeb7d298cdf897600123f3f613bb8d2b7903"
BASE = 0x4566FF74
COMMAND_TABLE = 0x45AE5B04
EVENT_SWITCH = 0x45914F14
REMOTE_ST = 0x45B7C2C0
REMOTE_PIPE = 0x45B7C300
J6_P = 0x45B7C408
J6_Q = 0x45B7C410
J6_STATE_PTR = 0x459B0C88
J6_TABLE_PTR = 0x459B0C8C


def word(image: bytes, address: int) -> int:
    offset = address - BASE
    if offset < 0 or offset + 4 > len(image):
        raise ValueError(f"address outside image: 0x{address:08x}")
    return struct.unpack_from("<I", image, offset)[0]


def cstring(image: bytes, address: int) -> str:
    offset = address - BASE
    if offset < 0 or offset >= len(image):
        raise ValueError(f"string outside image: 0x{address:08x}")
    end = image.index(0, offset, min(offset + 80, len(image)))
    return image[offset:end].decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller", type=Path, help="decoded XB22Q5 controller CROM segment 0")
    parser.add_argument("--ipl0-code", type=Path,
                        help="raw XB22Q5 first IPL code; checks the copied J6 gate's initial value")
    args = parser.parse_args()
    image = args.controller.read_bytes()
    actual = hashlib.sha256(image).hexdigest()
    if actual != EXPECTED_SHA256:
        parser.error(f"unexpected image SHA-256: {actual}")

    for expected_id, expected_name in ((2, "readsetup"), (3, "writesetup")):
        entry = COMMAND_TABLE + expected_id * 8
        command_id = word(image, entry)
        name = cstring(image, word(image, entry + 4))
        assert (command_id, name) == (expected_id, expected_name)
        print(f"command {command_id}: {name} (table 0x{entry:08x})")

    event7_target = word(image, EVENT_SWITCH + 7 * 4)
    assert event7_target == 0x45915184
    print(f"queue 0x6e event 7 -> 0x{event7_target:08x} (calls 0x45914970)")

    for entry, name, handler in (
        (REMOTE_ST, "st", 0x459AEF04),
        (REMOTE_PIPE, "||", 0x459B0A4C),
    ):
        actual_name = cstring(image, word(image, entry))
        actual_handler = word(image, entry + 4)
        assert (actual_name, actual_handler) == (name, handler)
        print(f"remote command {name!r} -> 0x{handler:08x}")

    for entry, letter, min_length, handler in (
        (J6_P, "p", 0, 0x459B14E8),
        (J6_Q, "q", 12, 0x459B1678),
    ):
        descriptor = word(image, entry)
        actual_handler = word(image, entry + 4)
        assert (descriptor, actual_handler) == (
            ord(letter) | (min_length << 8), handler
        )
        print(f"J6 subcommand {letter!r} -> 0x{handler:08x}")

    assert word(image, J6_STATE_PTR) == 0x43EDB914
    assert word(image, J6_TABLE_PTR) == 0x45B7C398
    print("J6 state base 0x43edb914, inner table base 0x45b7c398")

    if args.ipl0_code:
        ipl = args.ipl0_code.read_bytes()
        if hashlib.sha256(ipl).hexdigest() != IPL0_SHA256:
            parser.error("unexpected first IPL code SHA-256")
        source, destination, length = struct.unpack_from("<III", ipl, 0x56298)
        assert (source, destination, length) == (0x57004, 0x43E90000, 0x4C844)
        gate_address = 0x43EDB930
        assert destination <= gate_address < destination + length
        gate_offset = source + gate_address - destination
        initial_gate = struct.unpack_from("<I", ipl, gate_offset)[0]
        assert initial_gate == 0
        print(f"copied J6 gate at 0x{gate_address:08x}: initial value {initial_gate} "
              f"(IPL source offset 0x{gate_offset:x})")

    print("Static table entries alone do not establish acceptance of a setup write.")


if __name__ == "__main__":
    main()
