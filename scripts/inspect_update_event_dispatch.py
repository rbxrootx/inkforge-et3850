#!/usr/bin/env python3
"""Inspect controller event 0x76's ARM jump table in XB22Q5 CROM.

Accepts only segment 0 from extract_controller_crom.py. This is an offline
static check; it does not contact a printer or establish live reachability.
"""

import argparse
import hashlib
import struct
from pathlib import Path

PROVISIONAL_BASE = 0x45670000
LOAD_BASE = PROVISIONAL_BASE - 0x8C
SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
DISPATCH = 0x45809A10
TABLE = DISPATCH + 8  # ARM PC-relative LDR uses the address of this instruction + 8.
COUNT = 14


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    args = parser.parse_args()
    data = args.controller_segment.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        parser.error("input is not the expected XB22Q5 controller segment 0")

    def word(address: int) -> int:
        return struct.unpack_from("<I", data, address - PROVISIONAL_BASE)[0]

    assert word(DISPATCH) == 0x379FF100, "unexpected dispatcher instruction"
    print(f"event 0x76: runtime dispatcher {DISPATCH - 0x8C:#x}; "
          f"runtime table {TABLE - 0x8C:#x}")
    for index in range(COUNT):
        target = word(TABLE + index * 4)
        file_offset = target - LOAD_BASE
        region = "inside image" if 0 <= file_offset < len(data) else "outside image"
        print(f"  {index:2d}: runtime {target:#010x}; file offset {file_offset:#x} ({region})")
    assert word(TABLE + 8 * 4) == 0x45809A2C
    print("subcommand 8 selects the ROM1/ROM2 handler block at file offset 0x199ab8")


if __name__ == "__main__":
    main()
