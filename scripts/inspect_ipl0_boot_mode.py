#!/usr/bin/env python3
"""Inspect the XB22Q5 first IPL's boot-mode marker and relevant pointers.

Offline only. The user supplies a separately extracted first-IPL code image.
This script does not determine a live printer's mode.
"""

import argparse
import hashlib
from pathlib import Path


EXPECTED_SHA256 = "bf046b5bd5f5499c377bcbcb7b27aeb7d298cdf897600123f3f613bb8d2b7903"


def u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipl0", type=Path, help="separately extracted XB22Q5 first IPL")
    args = parser.parse_args()
    image = args.ipl0.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_SHA256:
        parser.error(f"unexpected first-IPL SHA-256: {digest}")

    marker_address = u32(image, 0xE84)
    mode_pointer_early = u32(image, 0xE78)
    mode_pointer_late = u32(image, 0x92D8)
    mode_pointer_update = u32(image, 0x26434)
    expected_family = image[0xE88 : 0xE8A]
    installed_family = image[marker_address : marker_address + 2]
    print(f"first IPL SHA-256: {digest}")
    print(f"mode pointers: 0x{mode_pointer_early:08x}, "
          f"0x{mode_pointer_late:08x}, 0x{mode_pointer_update:08x}")
    print(f"family marker pointer: 0x{marker_address:08x}")
    print(f"embedded family: {expected_family!r}")
    print(f"installed family: {installed_family!r}")
    print(f"installed version: {image[marker_address:marker_address + 8].split(bytes([0]), 1)[0]!r}")
    print(f"family matches: {expected_family == installed_family}")
    print("The startup selector can still choose mode 2 through other conditions; "
          "the live mode is not inferred by this marker check.")


if __name__ == "__main__":
    main()
