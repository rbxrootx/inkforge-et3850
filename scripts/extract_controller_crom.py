#!/usr/bin/env python3
"""Extract the XB22Q5 first-IPL controller image using an external CROM decoder.

Obtain ``uncrom.py`` separately from https://github.com/abrasive/epson-reversing.
This script does not include or distribute Epson firmware or that decoder.
"""

import argparse
import hashlib
import importlib.util
import io
from pathlib import Path


EXPECTED_RCX_SHA256 = "103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675"
CROM_OFFSET = 0x167112
NEXT_IPL_OFFSET = 0x754112
EXPECTED_SEGMENTS = (
    (5686304, "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"),
    (3036, "5c6af9a703999265215faeb814cb1e06cf38bbcfef8d78b703bcd031962caeb9"),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rcx", type=Path, required=True, help="Separately obtained XB22Q5 RCX")
    parser.add_argument("--uncrom", type=Path, required=True, help="Path to abrasive/epson-reversing/uncrom.py")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rcx = args.rcx.read_bytes()
    digest = sha256(rcx)
    if digest != EXPECTED_RCX_SHA256:
        parser.error(f"Unexpected RCX SHA-256: {digest}")
    region = rcx[CROM_OFFSET:NEXT_IPL_OFFSET]
    if not region.startswith(b"CROM"):
        parser.error("CROM magic missing at expected first-IPL offset")

    spec = importlib.util.spec_from_file_location("external_uncrom", args.uncrom)
    if spec is None or spec.loader is None:
        parser.error("Could not load CROM decoder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reader = module.CROMReader(io.BytesIO(region))
    segments = list(reader.unpack_all())
    if len(segments) != len(EXPECTED_SEGMENTS):
        parser.error(f"Expected two CROM segments, got {len(segments)}")
    for index, (segment, (length, expected_hash)) in enumerate(zip(segments, EXPECTED_SEGMENTS)):
        if len(segment) != length or sha256(segment) != expected_hash:
            parser.error(f"Decoded segment {index} failed length/hash check")
    if reader.stream.tell() != 0x264F10:
        parser.error(f"Unexpected CROM end offset: {reader.stream.tell():x}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for index, segment in enumerate(segments):
        path = args.output_dir / f"xb22q5-controller-{index}.bin"
        if path.exists():
            parser.error(f"Refusing to replace {path}")
        path.write_bytes(segment)
        print(f"{path}: {len(segment)} bytes SHA-256 {sha256(segment)}")
    print("ARM analysis base for segment 0: 0x45670000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
