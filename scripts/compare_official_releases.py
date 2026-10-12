"""Compare the signed headers of two separately obtained official ET-3850 RCX files.

This is an offline comparison. It does not test device trust or installability.
"""

import argparse
import hashlib
from pathlib import Path


def inspect(path: Path) -> dict:
    image = path.read_bytes()
    marker = image.find(b"EPSONSIGNXB20d")
    if marker < 0 or marker + 4096 > len(image):
        raise ValueError(f"{path}: XB20d signature block missing")
    payload = image[marker + 4096 :]
    declared = int.from_bytes(image[marker + 16 : marker + 20], "little")
    if declared != len(payload):
        raise ValueError(f"{path}: declared payload length mismatch")
    key = image[0xB122 : 0xB122 + 64]
    if len(key) != 64:
        raise ValueError(f"{path}: embedded public key missing")
    return {
        "image": image,
        "sha256": hashlib.sha256(image).hexdigest(),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "marker": marker,
        "signature": image[marker + 32 : marker + 96],
        "key": key,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("older", type=Path)
    parser.add_argument("newer", type=Path)
    args = parser.parse_args()
    old, new = inspect(args.older), inspect(args.newer)
    for label, record in (("older", old), ("newer", new)):
        print(label, "RCX SHA-256", record["sha256"])
        print(label, "payload SHA-256", record["payload_sha256"])
        print(label, "signature block", hex(record["marker"]))
        print(label, "embedded key SHA-256", hashlib.sha256(record["key"]).hexdigest())
    print("same embedded public key:", old["key"] == new["key"])
    print("same signature:", old["signature"] == new["signature"])
    start, end = 0x1112, 0x11112
    a, b = old["image"][start:end], new["image"][start:end]
    print("differing bytes in first 64 KiB of signed payload:",
          sum(x != y for x, y in zip(a, b)))


if __name__ == "__main__":
    main()
