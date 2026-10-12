"""Inspect Epson's signed RCX segment without copying firmware into this repo.

Usage: python scripts/inspect_signature_block.py path/to/FWCJ61TL.rcx
"""
import argparse
import hashlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rcx", type=Path)
    args = parser.parse_args()
    image = args.rcx.read_bytes()
    marker = b"EPSONSIGN"
    candidates = []
    start = 0
    while True:
        offset = image.find(marker, start)
        if offset < 0:
            break
        start = offset + 1
        if offset + 4096 > len(image):
            continue
        declared = int.from_bytes(image[offset + 16 : offset + 20], "little")
        actual = len(image) - (offset + 4096)
        if declared == actual:
            candidates.append((offset, declared))

    if not candidates:
        raise SystemExit("No 4096-byte EPSONSIGN block with a matching payload length")
    for offset, size in candidates:
        payload = image[offset + 4096 :]
        signature = image[offset + 32 : offset + 96]
        print(f"signature block offset: 0x{offset:x}")
        print("signature block size: 4096 bytes")
        print(f"declared and actual payload size: {size} bytes")
        print(f"64-byte signature field populated: {any(signature)}")
        print(f"payload SHA-256: {hashlib.sha256(payload).hexdigest()}")
        print("Cryptographic verification requires the matching public key.")


if __name__ == "__main__":
    main()
