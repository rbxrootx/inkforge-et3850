# Full-screen UI asset target

The XB22Q5 controller UI CROM at RCX offset `0x16da122` decodes to a 16,640,728-byte image. The four valid 320x240 PNGs in that decoded image are:

| Decoded offset | PNG bytes | Image |
| --- | ---: | --- |
| `0xb0e93c` | 22,014 | Blue wave |
| `0xb14494` | 104 | Solid black |
| `0xb144fc` | 104 | Solid dark blue (`#172a88`) |
| `0xb14564` | 104 | Solid white |

The owner reports a white home screen with blue tiles. This makes the earlier assumption that the blue-wave PNG is the active home wallpaper unsupported. The photo candidate replaces the blue wave and has been verified only as an offline CROM substitution. No custom image has been sent to the printer.

The ET-3850 [Basic Settings guide](https://download4.epson.biz/sec_pubs/et-3850_series/useg/en/GUID-F463AE8C-C46F-40CB-90CA-8FC8AEFD1052.htm) says `Settings > General Settings > Basic Settings > Wall Paper` changes the home background color. We still need to map those selections to the four PNGs or the actual drawing path before predicting where the photo would appear. The plain white PNG is too small to hold the prepared photo in its existing 104-byte slot, so replacing it would also require a verified resource relocation or renderer change.

[`scripts/list_full_screen_assets.py`](../scripts/list_full_screen_assets.py) inventories these offsets from a separately decoded image; the owner photo and firmware are not included in this repository.
