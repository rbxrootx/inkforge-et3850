# White-background LCD probe

The observed ET-3850 home screen is white with blue tiles. The XB22Q5 decoded UI CROM contains 320×240 solid black, blue, and white PNGs beside a blue-wave PNG. The wave is not the observed home background, so replacing it with a photo is not yet a proven reskin.

On 2026-10-12, we prepared a small offline probe for the **solid white** PNG at decoded offset `0xb14564`. [`recolor_solid_png.py`](../scripts/recolor_solid_png.py) changed its single palette entry from white to `#F05CFF`, preserving the 104-byte PNG size and 320×240 dimensions. The PNG differs in six bytes: its three color bytes and CRC. [`repack_photo_crom.py`](../scripts/repack_photo_crom.py) re-encoded the UI CROM and decoded it again. The entire 16,640,728-byte decoded image matched stock except for the 104-byte interval `0xb14564..0xb145cc`.

The modified CROM was merged into a copy of the image already verified running on the owner's printer. The resulting RCX has SHA-256 `39bff33211e6484a393647940e216123ac325e280582858da529e3cc1e78fcf2`; all three record checks and the local USB preflight pass. The normal ECDSA check still rejects it, as with the installed research image. The image is not distributed here.

The owner confirmed a normal home screen and USB connection. The USBPRINT D4 sender transferred all 40,607,745 binary bytes and received `fl:03:OK`. This is **transport acknowledgement only**.

**Adverse live result, 2026-10-12:** The owner then reported a black screen, no power-button light, and no response to one Power press. Windows showed no present Epson USB device. The printer has not been recovered or examined yet, so the exact failure point and cause are unknown. **Do not transfer this LCD marker image or any derivative.** No further firmware commands were sent after this report. Offline record checks did not predict this outcome.

The white asset was hypothesized to be the active wallpaper. The adverse live result means that hypothesis has not been tested visually. A full photo would require a verified resource mapping and a larger storage strategy; the 104-byte white PNG cannot hold it in place.

Read-only root inspection found `/dev/fb0` through `/dev/fb3` nodes, but no registered framebuffer in `/proc/devices`, `/proc/fb`, or `/sys/class/graphics`. Those nodes do not establish a live Linux framebuffer interface. The controller UI image remains the most concrete firmware skin target.

To reproduce the offline resource change with owner-supplied files:

```text
python scripts/recolor_solid_png.py stock-white-320x240.png white-marker.png --rgb F05CFF
python scripts/repack_photo_crom.py --source-crom ui-source.crom --decoded-ui ui-decoded.bin --wallpaper-png white-marker.png --png-offset 0xb14564 --uncrom uncrom.py --output ui-white-marker.crom
python scripts/merge_photo_candidate.py known-working-candidate.rcx ui-source.crom ui-white-marker.crom ui-white-marker.rcx --expected-base-sha256 SHA256_OF_BASE_IMAGE
```

The merger requires an exact base-image hash and verifies the enclosing record checks. These commands produce an offline image; they do not contact the printer.
