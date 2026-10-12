"""List valid 320x240 PNGs in a separately decoded ET-3850 UI CROM image."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import struct

from PIL import Image

from repack_photo_crom import png_end


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decoded_ui", type=Path)
    args = parser.parse_args()
    data = args.decoded_ui.read_bytes()
    signature = b"\x89PNG\r\n\x1a\n"
    cursor = 0
    while True:
        cursor = data.find(signature, cursor + 1)
        if cursor < 0:
            break
        try:
            end = png_end(data, cursor)
            image = Image.open(BytesIO(data[cursor:end]))
            if image.size == (320, 240):
                rgb = image.convert("RGB")
                print(f"{cursor:#x}\t{end - cursor}\t{image.mode}\t"
                      f"top-left={rgb.getpixel((0, 0))}\tcenter={rgb.getpixel((160, 120))}")
        except (ValueError, OSError, EOFError, struct.error):
            continue


if __name__ == "__main__":
    main()
