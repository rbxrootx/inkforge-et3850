#!/usr/bin/env python3
"""Check whether the XB22Q5/XB05O7 scanner CROM looks linked at 0x4370d000.

Supply separately decoded CROM segment-0 files. This is an offline check and
does not contact a printer or distribute firmware bytes.
"""

import argparse
import hashlib
from pathlib import Path
import re
import struct


EXPECTED = {
    "XB22Q5": ("8a6fd7facdf4534eb4c5e4f4261700fb839880f006e3e0ce19dea44f1c977c9d", 1313312),
    "XB05O7": ("c257530bfc0e7e4aaae00adea0e7be39066275dfc5c970320d4242bb550533b6", 1311768),
}
BASES = (0x43308000, 0x4343f000, 0x4370d000)


def check(label: str, path: Path) -> None:
    image = path.read_bytes()
    digest, length = EXPECTED[label]
    if len(image) != length or hashlib.sha256(image).hexdigest() != digest:
        raise ValueError(f"{path} does not match the expected {label} scanner image")

    pointers = {value for (value,) in
                struct.iter_unpack("<I", image[:len(image) // 4 * 4])}
    string_offsets = [match.start() for match in
                      re.finditer(rb"[ -~]{12,}", image)]
    counts = {base: sum(base + offset in pointers for offset in string_offsets)
              for base in BASES}
    if counts[0x43308000] != 77 or counts[0x4370d000] != 0:
        raise ValueError(f"Unexpected {label} base-anchor counts: {counts}")
    print(f"{label}: " + ", ".join(f"{base:#x}={count}"
                                     for base, count in counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xb22q5_scanner", type=Path)
    parser.add_argument("--xb05o7-scanner", type=Path)
    args = parser.parse_args()
    check("XB22Q5", args.xb22q5_scanner)
    if args.xb05o7_scanner:
        check("XB05O7", args.xb05o7_scanner)
    print("Pointer anchors do not map these images to the external 0x4370d000 region.")


if __name__ == "__main__":
    main()
