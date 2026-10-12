#!/usr/bin/env python3
"""Inspect the ambiguous controller request table in a decoded XB22Q5 CROM.

This is offline only. Obtain the controller segment separately with
extract_controller_crom.py. Nothing is sent to a printer.
"""

import argparse
import hashlib
from pathlib import Path


EXPECTED_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
BASE = 0x45670000
TABLE_LITERAL = 0x4590E67C
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

    table = word(image, TABLE_LITERAL)
    print(f"matcher table literal 0x{TABLE_LITERAL:08x} -> 0x{table:08x}")
    print("first eight-byte records as loaded by matcher:")
    for index in range(16):
        at = table + 8 * index
        first, second = word(image, at), word(image, at + 4)
        print(f"  {index:2} @ 0x{at:08x}: 0x{first:08x} {show_string(image, first)} | 0x{second:08x}")
    zero_prefix_index = next(
        (index for index in range(16)
         if image[word(image, table + 8 * index) - BASE] == 0), None
    )
    if zero_prefix_index is not None:
        print(f"record {zero_prefix_index} has a zero-length raw prefix; "
              "the decoded table cannot establish live dispatch behavior")

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

    # The request table also contains a pointer into the final four bytes of
    # GetRequestID. This is a byte-level fact, not proof that the handler runs.
    suffix_pointer = BASE + image.find(GET_REQUEST_NAME) + 8
    print(f"request-name suffix 0x{suffix_pointer:08x}: {show_string(image, suffix_pointer)}")
    print("No reachability or update-acceptance conclusion follows from this table alone.")


if __name__ == "__main__":
    main()
