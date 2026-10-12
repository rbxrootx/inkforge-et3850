#!/usr/bin/env python3
"""Check the XB22Q5 controller's setup command IDs and event-7 dispatch."""

import argparse
import hashlib
from pathlib import Path
import struct

EXPECTED_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
BASE = 0x4566FF74
COMMAND_TABLE = 0x45AE5B04
EVENT_SWITCH = 0x45914F14


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
    print("These are internal controller events, not evidence of a LAN route.")


if __name__ == "__main__":
    main()
