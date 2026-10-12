#!/usr/bin/env python3
"""Show that an XB22Q5 RCX text-envelope edit leaves its payload signature valid.

Usage: python scripts/check_rcx_envelope_scope.py path/to/FWCJ61TL.rcx
The package is not modified on disk and no printer is contacted.
Requires the cryptography package.
"""

import argparse
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


RCX_SHA256 = "103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675"
SIGNATURE_BLOCK = 0x112
PAYLOAD = SIGNATURE_BLOCK + 4096
KEY = 0xb122


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rcx", type=Path)
    args = parser.parse_args()
    original = args.rcx.read_bytes()
    if hashlib.sha256(original).hexdigest() != RCX_SHA256:
        parser.error("input is not the analyzed XB22Q5 RCX")
    if original[SIGNATURE_BLOCK:SIGNATURE_BLOCK + len(b"EPSONSIGNXB20d")] != b"EPSONSIGNXB20d":
        parser.error("unexpected signature-block position")
    envelope = original[:SIGNATURE_BLOCK]
    if not envelope.startswith(b"RCX\r\nSEIKO EPSON EpsonNet Form\r\n"):
        parser.error("unexpected outer envelope")
    marker = b'3="10"'
    position = envelope.find(marker)
    if position < 0:
        parser.error("expected envelope field not found")

    changed = bytearray(original)
    changed[position + 4] = ord("1")  # [B].3: 10 -> 11, same length.
    signature = original[SIGNATURE_BLOCK + 32:SIGNATURE_BLOCK + 96]
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    key_bytes = original[KEY:KEY + 64]
    key = ec.EllipticCurvePublicNumbers(
        int.from_bytes(key_bytes[:32], "big"),
        int.from_bytes(key_bytes[32:], "big"), ec.SECP256R1()
    ).public_key()
    digest = hashlib.sha256(changed[PAYLOAD:]).digest()
    key.verify(utils.encode_dss_signature(r, s), digest,
               ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    print(f"unsigned envelope bytes: {SIGNATURE_BLOCK}")
    print(f"changed offset: 0x{position + 4:x}")
    print(f"changed full-file SHA-256: {hashlib.sha256(changed).hexdigest()}")
    print(f"unchanged signed-payload SHA-256: {digest.hex()}")
    print("original signature still verifies; no RCX file was written")


if __name__ == "__main__":
    main()
