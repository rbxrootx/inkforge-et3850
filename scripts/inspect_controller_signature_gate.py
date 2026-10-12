#!/usr/bin/env python3
"""Check the XB22Q5 controller package verifier's key source offline.

This checks a decoded CROM segment and the separately extracted first IPL.
It does not execute the controller or establish that an HTTP request reaches
this package path.
"""

import argparse
import hashlib
import struct
from pathlib import Path


CONTROLLER_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
IPL_SHA256 = "bf046b5bd5f5499c377bcbcb7b27aeb7d298cdf897600123f3f613bb8d2b7903"
CONTROLLER_BASE = 0x45670000
HEADER_ADDRESS = 0x45778EE8
LITERALS_ADDRESS = 0x45778F00
IPL_KEY_DESCRIPTOR = 0x5628C


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller", type=Path, help="decoded XB22Q5 CROM segment 0")
    parser.add_argument("ipl", type=Path, help="raw XB22Q5 first IPL code image")
    args = parser.parse_args()
    controller = args.controller.read_bytes()
    ipl = args.ipl.read_bytes()
    for label, data, expected in (
        ("controller", controller, CONTROLLER_SHA256),
        ("IPL", ipl, IPL_SHA256),
    ):
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            parser.error(f"unexpected {label} SHA-256: {digest}")

    header_at = HEADER_ADDRESS - CONTROLLER_BASE
    literal_at = LITERALS_ADDRESS - CONTROLLER_BASE
    if controller[header_at : header_at + 9] != b"EPSONSIGN":
        raise ValueError("expected EPSONSIGN parser constant is absent")
    if controller[header_at + 12 : header_at + 14] != b"XB":
        raise ValueError("expected XB family constant is absent")
    if controller[header_at + 18 : header_at + 20] != b"20":
        raise ValueError("expected 20 family constant is absent")

    signature_dest, key_source, key_dest = struct.unpack_from("<III", controller, literal_at)
    source, destination, size = struct.unpack_from("<III", ipl, IPL_KEY_DESCRIPTOR)
    if (source, destination, size) != (0x13F000, 0x4FB26800, 0x1000):
        raise ValueError("unexpected IPL startup key copy descriptor")
    if key_source != destination or key_dest + 64 != signature_dest:
        raise ValueError("controller parser literals do not match expected key path")
    key = ipl[source : source + 64]
    if key != ipl[0x7010 : 0x7050]:
        raise ValueError("the two first-IPL key copies differ")

    print("Controller parser: EPSONSIGN + XB + 20 + d header")
    print(f"Controller parser key source: 0x{key_source:08x}")
    print(f"IPL startup copy: 0x{source:x} -> 0x{destination:08x}, 0x{size:x} bytes")
    print(f"Copied key SHA-256: {hashlib.sha256(key).hexdigest()}")
    print(f"Controller key destination: 0x{key_dest:08x}")
    print(f"Controller signature destination: 0x{signature_dest:08x}")
    print("This is a static key-source check, not proof of a live network update path.")


if __name__ == "__main__":
    main()
