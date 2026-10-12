#!/usr/bin/env python3
"""Check two or more XB20d RCX signatures for exact ECDSA r reuse."""

import argparse
import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


def inspect(path: Path) -> tuple[bytes, bytes, int, int]:
    image = path.read_bytes()
    marker = image.find(b"EPSONSIGNXB20d")
    if marker < 0 or marker + 4096 > len(image):
        raise ValueError(f"{path}: missing XB20d signature block")
    payload = image[marker + 4096 :]
    declared = int.from_bytes(image[marker + 16 : marker + 20], "little")
    if declared != len(payload):
        raise ValueError(f"{path}: payload length mismatch")
    signature = image[marker + 32 : marker + 96]
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    key = image[0xB122 : 0xB162]
    x = int.from_bytes(key[:32], "big")
    y = int.from_bytes(key[32:], "big")
    public_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
    digest = hashlib.sha256(payload).digest()
    try:
        public_key.verify(
            utils.encode_dss_signature(r, s),
            digest,
            ec.ECDSA(utils.Prehashed(hashes.SHA256())),
        )
    except InvalidSignature as exc:
        raise ValueError(f"{path}: signature does not verify") from exc
    return key, digest, r, s


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+", help="Two or more separately obtained RCX files")
    args = parser.parse_args()
    if len(args.images) < 2:
        parser.error("provide at least two RCX files")
    rows = [(path, inspect(path)) for path in args.images]
    for path, (key, digest, r, s) in rows:
        print(f"{path.name}: key_sha256={hashlib.sha256(key).hexdigest()} "
              f"payload_sha256={digest.hex()} r={r:064x} s={s:064x}")
    print("All signatures verify:", True)
    print("Same public key:", len({row[0] for _, row in rows}) == 1)
    repeated_r = [
        (a.name, b.name)
        for i, (a, first) in enumerate(rows)
        for b, second in rows[i + 1:]
        if first[0] == second[0] and first[1] != second[1] and first[2] == second[2]
    ]
    print("Repeated r on different payloads:", repeated_r)
    if repeated_r:
        print("WARNING: repeated r merits private-key recovery analysis.")
    else:
        print(f"No exact repeated-nonce signal in {len(rows)} samples.")


if __name__ == "__main__":
    main()
