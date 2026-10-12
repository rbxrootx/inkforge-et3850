#!/usr/bin/env python3
"""Advance a hash-checked QEMU copy to WebApp listener registration.

The input is patch_http_gates.py's offline output, never a device image.
These three additional shims replace an internal event call with the WebApp
worker, omit free() on the synthetic call argument, and model one missing
configuration reply. The output is for an isolated network namespace only.
"""

import argparse
import hashlib
from pathlib import Path


BASE = 0x10000
INPUT_SHA256 = "435851903b973a9a9a0d1d3b768bb9c067e84f96e2ec1e746bf382e62c5fd43c"
OUTPUT_SHA256 = "f23f3e1b1aed02ec4be9d46d5ff07fe3021b600cfeb15c67b77e72d725d1a398"
CALL_SITE = 0x9FBD8
WORKER = 0x16FC18


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("http_gates_copy", type=Path)
    parser.add_argument("output_copy", type=Path)
    args = parser.parse_args()
    data = bytearray(args.http_gates_copy.read_bytes())
    if hashlib.sha256(data).hexdigest() != INPUT_SHA256:
        parser.error("input is not the expected offline HTTP-gates copy")
    if args.output_copy.resolve() == args.http_gates_copy.resolve():
        parser.error("refusing to overwrite input")

    call_offset = CALL_SITE - BASE
    if data[call_offset : call_offset + 4].hex() != "573cfeeb":
        parser.error("unexpected bytes at WebApp worker call site")
    relative_words = (WORKER - CALL_SITE - 8) // 4
    if CALL_SITE + 8 + relative_words * 4 != WORKER:
        parser.error("worker call alignment error")
    data[call_offset : call_offset + 4] = (
        0xEB000000 | (relative_words & 0xFFFFFF)
    ).to_bytes(4, "little")

    patches = (
        (0x16FC30, "1e96faeb", "0000a0e1"),  # omit free(synthetic integer)
        (0x16FC78, "d5b1feeb", "0000a0e3"),  # missing config reply -> success
    )
    for address, expected, replacement in patches:
        offset = address - BASE
        if data[offset : offset + 4].hex() != expected:
            parser.error(f"unexpected bytes at {address:#x}")
        data[offset : offset + 4] = bytes.fromhex(replacement)

    digest = hashlib.sha256(data).hexdigest()
    if digest != OUTPUT_SHA256:
        parser.error("offline output digest mismatch")
    args.output_copy.write_bytes(data)
    print(f"offline QEMU copy: {args.output_copy} SHA-256 {digest}")


if __name__ == "__main__":
    main()
