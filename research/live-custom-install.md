# Live ET-3850 custom-install verification

On 2026-10-12, the owner-authorized ET-3850 at `192.168.0.12` accepted a USBPRINT D4 transfer of our custom XB22Q5-derived candidate. The final image was local `telnet4_wifi_auth_candidate.rcx`, SHA-256 `21ab2dce499dfdfce6fb68fe7407b075498981a20cba717fc30a249ad4cad055`; it is not distributed in this repository. The sender transferred 40,607,745 bytes and received `fl:03:OK`. The printer rebooted.

Transport acknowledgement alone was inconclusive, so the candidate included a startup hostname marker, a password-gated launcher on TCP 2323, and changed Wi-Fi module arguments. After reboot:

- Port 2323 displayed `ET3850MOD Password:`. A generated private password (not Epson's root password) authenticated.
- The resulting shell returned `uid=0(root) gid=0(root)`.
- `uname -a` reported Linux 4.4.27 on ARMv7 with hostname `ET3850MOD`.
- The live `/opt/nwsoc/nwsoc` MD5 was `d406bbfb28a966379b9d0df6171287a1`, matching the locally patched executable.
- `/sys/module/8723du/parameters/rtw_power_mgnt` and `/sys/module/8723du/parameters/rtw_enusbss` both read `0`.
- A JPEG cake print submitted over IPPS reached job state `9` (`completed`). The physical page was not independently checked in the tool trace.

The candidate fails normal ECDSA verification against the key in the extracted current firmware, while its three internal record checks passed. Isolated ARM emulation supports our length-gate and first-IPL branch interpretation, but the precise decision path taken by the live controller has not been observed. We can claim custom installation and root execution on this one physical device; we cannot yet claim a general, reliable installer for other units or a proven long-term Wi-Fi fix.

No SSH service has been installed. The existing printer runs Linux; this was a patch to that environment, not a replacement operating system. The owner photo wallpaper remains unverified because the observed white home screen does not match the blue-wave resource modified offline.
