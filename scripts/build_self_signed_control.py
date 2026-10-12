"""Build an offline self-signed XB20 RCX control with both IPL key copies changed.

This is a verification experiment, not installable firmware. It has not been
tested on a printer and may fail earlier boot or package integrity checks.
"""

import argparse
import hashlib
from pathlib import Path
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


KEY_OFFSETS = (0xB122, 0x143112)
SIGNATURE_OFFSET = 0x132
PAYLOAD_OFFSET = 0x1112
SQUASHFS_OFFSET = 0x1197112
XB22Q5_SHA256 = "103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675"


def public_key_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    numbers = key.public_numbers()
    return numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--squashfs", type=Path, help="offline replacement for the second SquashFS image")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    source = args.input.read_bytes()
    if source[0x112 : 0x112 + 14] != b"EPSONSIGNXB20d" or len(source) < KEY_OFFSETS[1] + 64:
        raise ValueError("not the expected XB20 RCX layout")
    if source[KEY_OFFSETS[0] : KEY_OFFSETS[0] + 64] != source[KEY_OFFSETS[1] : KEY_OFFSETS[1] + 64]:
        raise ValueError("original IPL key copies differ")

    private_key = ec.generate_private_key(ec.SECP256R1())
    replacement_key = public_key_bytes(private_key.public_key())
    modified = bytearray(source)
    if args.squashfs is not None:
        if hashlib.sha256(source).hexdigest() != XB22Q5_SHA256:
            raise ValueError("SquashFS replacement is pinned to XB22Q5")
        image = args.squashfs.read_bytes()
        if source[SQUASHFS_OFFSET : SQUASHFS_OFFSET + 4] != b"hsqs" or image[:4] != b"hsqs":
            raise ValueError("missing SquashFS superblock")
        old_used = struct.unpack_from("<Q", source, SQUASHFS_OFFSET + 40)[0]
        new_used = struct.unpack_from("<Q", image, 40)[0]
        if old_used != 2630538 or new_used < 4096 or new_used > old_used or new_used > len(image):
            raise ValueError(f"replacement image does not fit original slot: {new_used} > {old_used}")
        modified[SQUASHFS_OFFSET : SQUASHFS_OFFSET + old_used] = image[:new_used].ljust(old_used, b"\0")
        print(f"Replaced second SquashFS: {old_used} -> {new_used} bytes within original slot")
    for offset in KEY_OFFSETS:
        modified[offset : offset + 64] = replacement_key
    digest = hashlib.sha256(modified[PAYLOAD_OFFSET:]).digest()
    signature_der = private_key.sign(digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    r, s = utils.decode_dss_signature(signature_der)
    modified[SIGNATURE_OFFSET : SIGNATURE_OFFSET + 64] = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    private_key.public_key().verify(signature_der, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(modified)
    print("Original SHA-256:", hashlib.sha256(source).hexdigest())
    print("Control SHA-256:", hashlib.sha256(modified).hexdigest())
    print("Ephemeral public key SHA-256:", hashlib.sha256(replacement_key).hexdigest())
    print("Both IPL key copies changed and payload signature verifies with that key.")
    print("No private key was saved. No printer contact was made.")


if __name__ == "__main__":
    main()
