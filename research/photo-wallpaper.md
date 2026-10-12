# Owner photo wallpaper candidate

The owner supplied a photo of two people for the ET-3850 home-screen wallpaper. A blue-wave asset is a 320x240, 22,014-byte indexed PNG inside the third RCX record's UI CROM. The owner reports that the actual home screen is white with blue tiles and the `Wall Paper` menu offers only solid colors. The blue wave is **not the observed active home background**. This repository does not include the original photograph or a firmware image.

The local `outputs/et3850-wallpaper-photo-preview.png` preserves the owner's original photo, cropped to 4:3 and resized to 320x240. The local `outputs/et3850-wallpaper-32color.png` is 20,644 bytes. Both files are kept outside this research repository. `scripts/prepare_photo_wallpaper.py` reproduces them from an owner-supplied source photo; Pillow is required.

`scripts/repack_photo_crom.py` pads the photo PNG with a valid `tEXt` chunk to exactly 22,014 bytes, then re-encodes the existing CROM copy/literal stream. It preserves unchanged tokens and converts only copy items whose output would otherwise differ into literal items. On the pinned XB22Q5 UI CROM, 587 copied bytes were converted to literals, the compressed stream grew by 318 bytes, and the final CROM region retained its original length using existing `0xff` filler. The external `uncrom.py` decoder reproduced the complete 16,640,728-byte UI image; the sole decoded difference was the wallpaper PNG interval at `0xb0e93c..0xb13f3a`. Its SHA-256 is `f2945ab6d0cdf633c86d647171e35a4f36dcb6894005544d8b3f4d3aa6cfcc`.

`scripts/merge_photo_candidate.py` inserted that CROM into the prior offline Wi-Fi/Telnet length-gate candidate. The resulting 40,608,019-byte RCX has SHA-256 `b3dfbc88b93eda08dabe5e47045e5579ceda134ff3fac4df357a2979fb579972`; all three enclosing record byte sums and SHA-1 digests pass. The file remains local scratch material. Normal ECDSA verification **rejects** it, and this photo image has not been sent to the printer. A separate Wi-Fi/Telnet candidate was transferred over USB, with device-side acceptance still unknown. The isolated length-gate finding does not establish boot-ROM acceptance, installation, or display of this wallpaper. The resource target must be corrected or selected before display on the white-and-blue home screen is a credible outcome.

Offline reconstruction example, using separately obtained firmware and decoder files:

```text
python scripts/prepare_photo_wallpaper.py personal-photo.png photo-320x240.png --preview preview.png
python scripts/repack_photo_crom.py --source-crom ui-source.crom --decoded-ui ui-decoded.bin --wallpaper-png photo-320x240.png --uncrom uncrom.py --output ui-photo.crom
python scripts/merge_photo_candidate.py telnet-wifi-candidate.rcx ui-source.crom ui-photo.crom telnet-wifi-photo-candidate.rcx
```
