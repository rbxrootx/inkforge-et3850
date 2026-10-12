#!/usr/bin/env python3
"""Check the XB22Q5 controller's generic /UP/ route table offline."""

import argparse
import hashlib
from pathlib import Path
import struct


EXPECTED_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
LOAD_BASE = 0x4566FF74


def inspect(path: Path) -> None:
    image = path.read_bytes()
    if hashlib.sha256(image).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Input is not the expected XB22Q5 controller CROM segment")

    def word(address: int) -> int:
        return struct.unpack_from("<I", image, address - LOAD_BASE)[0]

    def string(address: int) -> bytes:
        offset = address - LOAD_BASE
        if not 0 <= offset < len(image):
            raise ValueError(f"String pointer outside image: {address:#x}")
        return image[offset:image.index(b"\0", offset)]

    table = word(0x459122FC)
    assert table == 0x45AE5AB4
    expected = (b"/UP/PRINTENHANCED1", b"/UP/PRINTBASIC1")
    for index, route in enumerate(expected):
        entry = table + index * 0x28
        observed = string(word(entry + 6 * 4))
        if observed != route:
            raise ValueError(f"Unexpected /UP/ entry {index}: {observed!r}")
        print(f"{entry:#x}: {observed.decode()}")

    down = string(word(0x4591336C))
    if down != b"/DOWN/FIRMWAREUPDATE/":
        raise ValueError(f"Unexpected firmware write prefix: {down!r}")
    if b"/UP/FIRMWAREUPDATE/" in image:
        raise ValueError("A firmware readback string is present; inspect it")
    print("The mapped /UP/ entries are print-service routes; no /UP/FIRMWAREUPDATE/ literal was found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    inspect(parser.parse_args().controller_segment)
