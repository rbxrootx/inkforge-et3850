#!/usr/bin/env python3
"""Decode two HTTP service route-name selections in XB22Q5 nwsoc.

The lists are operands of strcmp calls in nwsoc at 0x16de88 and 0x16f51c.
They do not establish which handler matches a live HTTP request.
"""

import argparse
import hashlib
from pathlib import Path


SHA256 = "70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0"
BASE = 0x10000
INCLUDE_SLOTS = (0x16E474, 0x16E478, 0x16E47C, 0x16E480, 0x16E484,
               0x16E488, 0x16E48C, 0x16E490, 0x16E494, 0x16E498,
               0x16E49C, 0x16E4B0)
EXCLUDE_SLOTS = tuple(range(0x16F7CC, 0x16F7F8, 4))


def read_route(blob: bytes, slot: int) -> str:
    offset = slot - BASE
    pointer = int.from_bytes(blob[offset : offset + 4], "little")
    start = pointer - BASE
    if not 0 <= start < len(blob):
        raise ValueError(f"bad pointer at {slot:#x}: {pointer:#x}")
    end = blob.find(b"\0", start, start + 128)
    if end < 0:
        raise ValueError(f"unterminated string at {pointer:#x}")
    return blob[start:end].decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nwsoc", type=Path)
    args = parser.parse_args()
    blob = args.nwsoc.read_bytes()
    if hashlib.sha256(blob).hexdigest() != SHA256:
        parser.error("input is not the expected original XB22Q5 nwsoc")
    for label, slots in (("0x16de88 registers matching paths", INCLUDE_SLOTS),
                         ("0x16f51c registers nonmatching paths", EXCLUDE_SLOTS)):
        print(label)
        for slot in slots:
            print(f"  {slot:#010x} {read_route(blob, slot)}")


if __name__ == "__main__":
    main()
