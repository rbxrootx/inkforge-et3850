"""Draw a letter-size cake page for the final ET-3850 print."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 2550, 3300  # US Letter at 300 dpi


def font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_cake(path: Path):
    im = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
    d = ImageDraw.Draw(im)
    ink = "#29243d"
    pink = "#f6a8b8"
    peach = "#ffe0c4"
    cream = "#fff8e9"
    blue = "#afdaf1"

    d.text((WIDTH // 2, 280), "CAKE!", anchor="ma", font=font(310), fill=ink)
    d.ellipse((260, 2600, 2290, 2810), fill="#e4dcef", outline=ink, width=18)
    d.rounded_rectangle((450, 1720, 2100, 2640), radius=95, fill=pink, outline=ink, width=20)
    d.rectangle((455, 2110, 2095, 2210), fill="#e985a0")
    d.line((455, 2110, 2095, 2110), fill=ink, width=15)
    d.line((455, 2210, 2095, 2210), fill=ink, width=15)
    d.rounded_rectangle((640, 1270, 1910, 1810), radius=80, fill=blue, outline=ink, width=20)
    d.rounded_rectangle((630, 1200, 1920, 1390), radius=85, fill=cream, outline=ink, width=18)
    for x in range(700, 1840, 190):
        d.ellipse((x, 1300, x + 145, 1455), fill=cream, outline=ink, width=14)
    for x in (770, 1050, 1330, 1610):
        d.ellipse((x, 2300, x + 120, 2420), fill=peach, outline=ink, width=15)
        d.ellipse((x + 40, 2250, x + 80, 2310), fill="#d84e6a")

    for x, color in ((965, "#f6d46b"), (1250, "#bdc8ed"), (1535, "#f7b8aa")):
        d.rounded_rectangle((x - 55, 875, x + 55, 1235), radius=30, fill=color, outline=ink, width=16)
        d.line((x, 875, x, 812), fill=ink, width=12)
        d.ellipse((x - 35, 728, x + 35, 830), fill="#ffbf50", outline=ink, width=12)

    for x, y in ((540, 900), (2000, 1110), (470, 1450), (2050, 1540), (790, 680), (1830, 740)):
        d.line((x - 45, y, x + 45, y), fill="#bf83ac", width=16)
        d.line((x, y - 45, x, y + 45), fill="#bf83ac", width=16)

    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", quality=92, subsampling=0, dpi=(300, 300))
    print(f"created {path} ({WIDTH}x{HEIGHT})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    draw_cake(args.output)


if __name__ == "__main__":
    main()
