#!/usr/bin/env python3
"""List XB22Q5 controller remote commands from its hash-locked CROM image."""

import argparse
import hashlib
from pathlib import Path
import struct

BASE = 0x4566FF74
EXPECTED_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
COUNT_PTR = 0x459AED10
TABLE_PTR = 0x459AED14


def word(image: bytes, address: int) -> int:
    offset = address - BASE
    if offset < 0 or offset + 4 > len(image):
        raise ValueError(f"address outside decoded segment: 0x{address:08x}")
    return struct.unpack_from("<I", image, offset)[0]


def key_name(image: bytes, address: int) -> str:
    offset = address - BASE
    if offset < 0 or offset + 2 > len(image):
        return "<outside segment>"
    return repr(image[offset:offset + 2].decode("ascii", errors="replace"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller", type=Path, help="decoded XB22Q5 controller CROM segment 0")
    args = parser.parse_args()
    image = args.controller.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_SHA256:
        parser.error(f"unexpected image SHA-256: {digest}")

    count_addr = word(image, COUNT_PTR)
    table = word(image, TABLE_PTR)
    count = word(image, count_addr)
    assert (count_addr, table, count) == (0x45B7C330, 0x45B7C2B8, 15)
    print(f"remote table: {count} entries at 0x{table:08x}")
    for index in range(count):
        entry = table + index * 8
        key_address = word(image, entry)
        handler = word(image, entry + 4)
        print(f"{index:02d} {key_name(image, key_address):20s} "
              f"key-address=0x{key_address:08x} handler=0x{handler:08x}")
    print("Table membership alone does not prove live acceptance or authorization.")


if __name__ == "__main__":
    main()
