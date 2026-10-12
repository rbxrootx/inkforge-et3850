#!/usr/bin/env python3
"""Make an offline-only nwsoc copy for QEMU HTTP startup research.

This bypasses missing controller RSC data and three network-state semaphores.
The result is not a firmware candidate and must never be installed on a printer.
"""

import argparse
import hashlib
from pathlib import Path


ORIGINAL_SHA256 = "70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0"
PATCHED_SHA256 = "435851903b973a9a9a0d1d3b768bb9c067e84f96e2ec1e746bf382e62c5fd43c"
BASE = 0x10000
PATCHES = (
    (0x98308, "14bdfeeb", "0100a0e3", "fail absent PRT_MARKERTECH RSC lookup"),
    (0x9F818, "d21300eb", "0000a0e3", "bypass HTTP-start semaphore"),
    (0x9F860, "c01300eb", "0000a0e3", "bypass link semaphore"),
    (0x9F878, "ba1300eb", "0000a0e3", "bypass IP semaphore"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_nwsoc", type=Path)
    parser.add_argument("output_copy", type=Path)
    args = parser.parse_args()
    data = bytearray(args.original_nwsoc.read_bytes())
    if hashlib.sha256(data).hexdigest() != ORIGINAL_SHA256:
        parser.error("input is not the expected original XB22Q5 nwsoc")
    if args.output_copy.resolve() == args.original_nwsoc.resolve():
        parser.error("refusing to overwrite the original")
    for address, expected, replacement, _reason in PATCHES:
        offset = address - BASE
        if data[offset : offset + 4].hex() != expected:
            parser.error(f"unexpected bytes at {address:#x}")
        data[offset : offset + 4] = bytes.fromhex(replacement)
    digest = hashlib.sha256(data).hexdigest()
    if digest != PATCHED_SHA256:
        parser.error("patched copy digest mismatch")
    args.output_copy.write_bytes(data)
    print(f"offline QEMU copy: {args.output_copy} SHA-256 {digest}")


if __name__ == "__main__":
    main()
