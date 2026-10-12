"""Verify an XB20d RCX signature with its embedded P-256 public key.

Requires the third-party cryptography package. This checks internal consistency;
the public key is also inside the image, so it does not establish a trusted root.
"""
import argparse
import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rcx", type=Path)
    parser.add_argument("--key-offset", type=lambda value: int(value, 0),
                        default=0xB122, help="ET-3850 XB20d key coordinate offset")
    args = parser.parse_args()

    image = args.rcx.read_bytes()
    block = image.find(b"EPSONSIGNXB20d")
    if block < 0 or block + 4096 > len(image):
        raise SystemExit("XB20d signature block missing or truncated")
    declared = int.from_bytes(image[block + 16 : block + 20], "little")
    payload = image[block + 4096 :]
    if declared != len(payload):
        raise SystemExit("Declared payload length does not match file")

    signature = image[block + 32 : block + 96]
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    key_data = image[args.key_offset : args.key_offset + 64]
    if len(key_data) != 64:
        raise SystemExit("Public key coordinate data missing")
    x = int.from_bytes(key_data[:32], "big")
    y = int.from_bytes(key_data[32:], "big")
    key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
    digest = hashlib.sha256(payload).digest()
    try:
        key.verify(utils.encode_dss_signature(r, s), digest,
                   ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    except InvalidSignature:
        raise SystemExit("Signature invalid for selected payload and key")
    print("RCX signature verifies against the embedded P-256 public key")
    print(f"signature block: 0x{block:x}; payload bytes: {len(payload)}")
    print(f"public key offset: 0x{args.key_offset:x}")
    print(f"public key SHA-256: {hashlib.sha256(key_data).hexdigest()}")
    print("Embedded-key verification alone does not prove device trust or upload access.")


if __name__ == "__main__":
    main()
