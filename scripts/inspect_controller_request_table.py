#!/usr/bin/env python3
"""Inspect controller request dispatch tables in decoded XB22Q5 CROM.

This is offline only. Obtain the controller segment separately with
extract_controller_crom.py. Nothing is sent to a printer.
"""

import argparse
import hashlib
from pathlib import Path


EXPECTED_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
BASE = 0x4566FF74
PROVISIONAL_BASE = 0x45670000
TABLES = (
    ("four-byte prefix", 0x4590ED78, 5),
    ("EpsonLocalReq command", 0x4590ED7C, 0x26),
    ("HTTP response prefix", 0x4590E67C, 1),
)
GET_REQUEST_NAME = b"GetRequestID"
FIRMWARE_NAME = b"/FIRMWAREUPDATE"


def word(image: bytes, address: int) -> int:
    offset = address - BASE
    if offset < 0 or offset + 4 > len(image):
        raise ValueError(f"address outside segment: {address:08x}")
    return int.from_bytes(image[offset : offset + 4], "little")


def show_string(image: bytes, address: int) -> str:
    offset = address - BASE
    if offset < 0 or offset >= len(image):
        return "<outside segment>"
    return repr(image[offset : offset + 64].split(b"\0", 1)[0].decode("ascii", "backslashreplace"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segment", type=Path, help="decoded XB22Q5 controller segment 0")
    args = parser.parse_args()
    image = args.segment.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_SHA256:
        parser.error(f"unexpected controller SHA-256: {digest}")

    for label, provisional_literal, count in TABLES:
        literal = provisional_literal - (PROVISIONAL_BASE - BASE)
        table = word(image, literal)
        print(f"{label} table: literal 0x{literal:08x} -> 0x{table:08x}; {count} records")
        for index in range(count):
            at = table + 8 * index
            name, callback = word(image, at), word(image, at + 4)
            if not BASE <= callback < BASE + len(image):
                raise ValueError(f"callback outside CROM at record {index}: {callback:#x}")
            print(f"  {index:2} @ 0x{at:08x}: 0x{name:08x} "
                  f"{show_string(image, name)} | callback 0x{callback:08x} "
                  f"(provisional 0x{callback + PROVISIONAL_BASE - BASE:08x})")

    for name in (GET_REQUEST_NAME, FIRMWARE_NAME):
        offset = image.find(name)
        while offset >= 0:
            address = BASE + offset
            pointer = address.to_bytes(4, "little")
            references = []
            start = 0
            while (found := image.find(pointer, start)) >= 0:
                references.append(BASE + found)
                start = found + 1
            print(f"{name.decode()} @ 0x{address:08x}: exact pointer sites "
                  f"{[f'0x{site:08x}' for site in references]}")
            offset = image.find(name, offset + 1)

    print("These static pointers identify controller dispatch callbacks. They do not "
          "show a successful live request or image acceptance.")


if __name__ == "__main__":
    main()
