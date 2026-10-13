# InkForge ET-3850: owner workbench

This is the build and control workflow for the ET-3850 on which a custom image and root shell were verified. The code contains the updater acceptance research, but Epson firmware images and owner credentials remain local.

## Launch the UI

From this directory on Windows:

```powershell
python et3850_mod.py gui
```

The **PATCH LAB** page accepts the pinned XB22Q5 stock RCX. **BUILD FULL MOD** extracts its two SquashFS images, generates or reuses a private password file in this project's `work/` directory, patches the root login and Wi-Fi files, repacks both filesystems in WSL, and builds an RCX. It writes a matching `.manifest.json` beside the image. It does not contact the printer.

The **FLASH PATH** page checks the image and manifest before a USBPRINT D4 transfer. **SEND TO ATTACHED PRINTER** starts an update transfer only after an explicit UI confirmation. The UI reports the transport acknowledgement; use the **SHELL** page after reboot to verify the installed result. A fresh build is not yet device-tested, even though the same code path installed the earlier research candidate.

The **SHELL** page connects to the password-gated port 2323 service on an already modified printer. The command field accepts arbitrary shell commands as root. Presets show files, processes, Wi-Fi parameters, boot messages, and mounted firmware storage. The password is read from the local file and is never printed or stored in the code repository. The connection uses Telnet on the local network, so commands and credentials travel in plaintext.

## Command line

```powershell
python inkforge.py build ..\..\work\FWCJ61TL.rcx ..\..\work\my-et3850.rcx --password-file ..\..\work\my-password.txt
python inkforge.py install ..\..\work\my-et3850.rcx
python inkforge.py install ..\..\work\my-et3850.rcx --send
python inkforge.py postflight 192.168.0.12 --password-file ..\..\work\my-password.txt
python et3850_mod.py shell 192.168.0.12 --password-file ..\..\work\my-password.txt
```

The first `install` form is preflight only. `--send` transmits. The builder requires WSL with `unsquashfs`, `mksquashfs`, and `openssl`; WSL root is used to preserve SquashFS device-node metadata. Python needs `cryptography` for the embedded-key signature check, and Python 3.12 or earlier for `telnetlib`.

## Scope and current limits

- Source RCX SHA-256: `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675` (XB22Q5 only). Other firmware versions are rejected.
- The installed research image returned `uid=0(root)` and the patched network executable's MD5 was `d406bbfb28a966379b9d0df6171287a1`. The new offline InkForge build produced the same executable MD5 and passed RCX record checks, but its full image hash differs because the filesystems were repacked.
- No SSH server is installed. The root console is the password-gated port 2323 shell.
- The Wi-Fi module's two power parameters read `0` live. Long-term reliability has not been measured.
- The owner's photo wallpaper is still a research lead; the printer's observed home screen has not shown it.
- We have no tested recovery procedure for a failed custom install. Preserve the stock RCX and the existing working image in private storage.

The RCX, password, manifest, and extracted Epson files remain in local `work/` and are excluded from Git. The simpler [companion repository](https://github.com/rbxrootx/et3850-mod-lab) has controls for an already modified printer.
