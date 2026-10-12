#!/usr/bin/env python3
"""Inventory every CROM region in a separately obtained XB22Q5 RCX.

Requires the external abrasive/epson-reversing ``uncrom.py`` decoder. This
script prints hashes and selected string counts; it does not write firmware.
"""

import argparse
import hashlib
import importlib.util
import io
from pathlib import Path


EXPECTED_RCX_SHA256 = "103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675"
MAGIC = b"CROM\xff\xd8"
NEEDLES = (b"GetRequestID", b"/DOWN/FIRMWAREUPDATE/", b"/FIRMWAREUPDATE",
           b"WriteSetup", b"EpsonLocalReq", b"Method:", b"URI:")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rcx", required=True, type=Path)
    parser.add_argument("--uncrom", required=True, type=Path)
    args = parser.parse_args()
    image = args.rcx.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_RCX_SHA256:
        parser.error(f"unexpected RCX SHA-256: {digest}")

    spec = importlib.util.spec_from_file_location("external_uncrom", args.uncrom)
    if spec is None or spec.loader is None:
        parser.error("could not load CROM decoder")
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)

    positions = []
    offset = 0
    while (offset := image.find(MAGIC, offset)) >= 0:
        positions.append(offset)
        offset += len(MAGIC)
    print("CROM headers:", ", ".join(f"0x{p:x}" for p in positions))
    for index, start in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else len(image)
        reader = decoder.CROMReader(io.BytesIO(image[start:end]))
        try:
            segments = list(reader.unpack_all())
        except Exception as exc:
            print(f"0x{start:x}: decode failed: {type(exc).__name__}: {exc}")
            continue
        print(f"0x{start:x}: {len(segments)} decoded segment(s), consumed 0x{reader.stream.tell():x} bytes")
        for part, segment in enumerate(segments):
            payload = bytes(segment)
            matches = {key.decode(): payload.count(key) for key in NEEDLES if payload.count(key)}
            print(f"  {part}: size={len(payload)} sha256={hashlib.sha256(payload).hexdigest()} strings={matches}")


if __name__ == "__main__":
    main()
