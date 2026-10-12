#!/usr/bin/env python3
"""Make a 320x240, 32-color PNG from an owner-supplied photo."""

import argparse
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photo", type=Path)
    parser.add_argument("output_png", type=Path)
    parser.add_argument("--preview", type=Path, help="optional true-color 320x240 preview")
    args = parser.parse_args()
    with Image.open(args.photo) as original:
        rgb = original.convert("RGB")
        width, height = rgb.size
        crop_height = min(height, width * 3 // 4)
        crop_width = min(width, height * 4 // 3)
        top = max(0, min(height - crop_height, int(height * 0.08)))
        left = (width - crop_width) // 2
        lcd = rgb.crop((left, top, left + crop_width, top + crop_height))
        lcd = lcd.resize((320, 240), Image.Resampling.LANCZOS)
        if args.preview:
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            lcd.save(args.preview, optimize=True)
        palette = lcd.quantize(colors=32, method=Image.Quantize.MEDIANCUT,
                               dither=Image.Dither.NONE)
        args.output_png.parent.mkdir(parents=True, exist_ok=True)
        palette.save(args.output_png, optimize=True, compress_level=9)
        print("crop", (left, top, left + crop_width, top + crop_height))
        print("wallpaper", args.output_png, args.output_png.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
