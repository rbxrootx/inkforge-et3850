# InkForge ET-3850

Build and inspect a custom ET-3850 firmware image, transfer it over USB, and open a root console on a modified printer. InkForge is a Python/Tkinter workbench for owners experimenting with firmware `05.15.XB22Q5`. It does not include Epson firmware, a flashable image, or device credentials.

**Tested on one ET-3850:** A custom XB22Q5-derived image was transferred over USBPRINT D4. After reboot, the device ran our patched network executable, exposed a password-gated shell on TCP 2323, and reported `rtw_power_mgnt=0` and `rtw_enusbss=0`. The package did not verify against the extracted stock ECDSA key. The exact device-side acceptance path was not captured. [Evidence and limits](research/live-custom-install.md).

The current one-click builder produces an image that passes its offline checks, but **that exact freshly built image has not been flashed**. There is no tested recovery procedure for a failed custom install. This is an XB22Q5 research tool, not a general Epson unlock.

## What it does

| Module | Function |
| --- | --- |
| Device Deck | Shows Windows USB and printer-queue metadata; can query the live D4 status. |
| Patch Lab | Builds a custom RCX from a separately obtained, hash-pinned XB22Q5 RCX. Adds the root launcher and changes Wi-Fi driver power arguments. |
| Flash Path | Checks the RCX and manifest. Sending requires a separate confirmation in the UI. |
| Shell | Connects to the installed TCP 2323 service with a locally stored password. Includes command presets and an interactive terminal. |
| LCD Theme | Previews an offline theme candidate. A photo on the actual home screen is **not verified**. |

## Run it

Requirements: Windows, Python 3.12 or earlier, and a USB-connected ET-3850 for installation. The full builder also needs WSL with `unsquashfs`, `mksquashfs`, and `openssl`. Install Python `cryptography` for the image signature check; `Pillow` enables image previews.

```powershell
python -m pip install cryptography Pillow
python et3850_mod.py gui
```

Put your own XB22Q5 RCX in the work directory shown by the app. By default, that is an `inkforge-work` folder **beside** the cloned repository; set `INKFORGE_WORK_DIR` to use another folder outside the repository. The source RCX must have SHA-256 `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675`. InkForge rejects other releases.

In **Patch Lab**, select the source RCX and a new output path in the work directory, then choose **Build Full Mod**. This generates a password file, repacks both SquashFS images, writes the RCX and a matching `.manifest.json`, and runs offline integrity checks. **Flash Path → Preflight Candidate** does not contact the printer; **Send to Attached Printer** streams the image over USB. After the printer reboots, enter its local IP address in **Shell** and verify `id` and the Wi-Fi parameters. The [step-by-step workflow](research/inkforge-workflow.md) includes command-line equivalents.

Keep the generated password file: InkForge does not contain a recovery password. The TCP 2323 console uses Telnet and sends the password and commands in plaintext. Use it on a network you control; do not expose that port to the internet.

## Access boundary

The installer needs **physical USB access** to the printer in the tested path. The root client needs the printer's **reachable IP address and the generated password**, and only works after the mod is installed. Being on the same Wi-Fi is a common way to reach it, but the actual requirement is IP connectivity; network isolation or a firewall can block it. InkForge does not grant access to arbitrary printers, does not discover or guess passwords, and has no verified network-only install path. SSH is not installed.

## Research and reporting

- [Live install evidence](research/live-custom-install.md) — what the physical device proved.
- [Firmware layout and USB transport](research/firmware-layout.md) · [USB update route](research/usb-update-route.md).
- [Firmware acceptance analysis](research/controller-signature-length-bypass.md) — isolated ARM controls and unresolved checks.
- [LCD asset research](research/full-screen-ui-assets.md) · [white-background probe](research/lcd-theme-probe.md) — why the photo candidate is not yet a home-screen skin.
- [Finding tracker](research/vulnerabilities.md) — separates reproduced behavior from static leads and retracted findings.
- [Disclosure guide](SECURITY.md) — how to report a new InkForge or Epson issue.

The repo includes reproducible scripts and research notes. Some notes record earlier hypotheses and candidate states; use the linked live evidence for current device claims. No Epson firmware or owner photo is distributed here. InkForge is an independent project and is not affiliated with Epson.

## License

MIT for this repository's original code and documentation. Epson firmware remains Epson's property and is not covered by this license.
