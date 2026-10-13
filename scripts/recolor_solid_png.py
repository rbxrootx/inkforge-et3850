"""Recolor a one-palette-entry PNG without changing its bytes or dimensions."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import zlib


SIGNATURE = b"\x89PNG\r\n\x1a\n"


def recolor(blob: bytes, rgb: bytes) -> bytes:
    if len(rgb) != 3 or not blob.startswith(SIGNATURE):
        raise ValueError("expected an RGB color and PNG input")
    output = bytearray(blob)
    cursor = len(SIGNATURE)
    found = False
    while cursor < len(output):
        size = struct.unpack_from(">I", output, cursor)[0]
        kind = bytes(output[cursor + 4:cursor + 8])
        data_start = cursor + 8
        end = data_start + size
        if end + 4 > len(output):
            raise ValueError("truncated PNG chunk")
        if kind == b"PLTE":
            if found or size != 3:
                raise ValueError("expected exactly one palette entry")
            output[data_start:end] = rgb
            struct.pack_into(">I", output, end, zlib.crc32(kind + rgb))
            found = True
        cursor = end + 4
        if kind == b"IEND":
            break
    if not found or cursor != len(output):
        raise ValueError("not a complete one-color PNG")
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rgb", required=True, help="six-digit RGB hex color, for example F05CFF")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("source and output must differ")
    if len(args.rgb) != 6:
        parser.error("--rgb must contain six hex digits")
    try:
        rgb = bytes.fromhex(args.rgb)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_bytes(recolor(args.source.read_bytes(), rgb))
    print(args.output, "bytes", args.output.stat().st_size, "rgb", args.rgb.upper())


if __name__ == "__main__":
    main()
