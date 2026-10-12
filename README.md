# Epson ET-3850 firmware research

Research into the ET-3850 network firmware and a possible Wi-Fi power-management modification. This repository contains original analysis and tools only. It does not distribute Epson firmware, device credentials, or a flashable image.

## Current state

- Extracted Epson's official XB22Q5 recovery package. The live printer reports `05.15.XB22Q5`.
- Compared an older official XB05O7 package with XB22Q5. The embedded signing key, suspend scripts, Realtek firmware blob, Wi-Fi module arguments, and HTTP/API-shaped string set are stable; the 8723DU kernel module changed. See [the release comparison](research/official-release-comparison.md).
- Rehosted the ARM `nwsoc` application under QEMU. Scratch-only ioctl stubs advance it through EPIDC channel open and message send; it now waits for the physical controller's `EPSON-INFORMATION` reply before Wi-Fi initialization. See [the application rehost trace](research/application-rehost.md).
- Identified a candidate change to the Realtek 8723DU module arguments: `rtw_power_mgnt=1 rtw_enusbss=1` to `0,0`. **This has not been validated as a fix.** The executable has 8821CU loader strings, but direct SquashFS listings contain only the 8723DU module and firmware. The test printer's actual USB product identifier is unknown.
- Built a second offline candidate that changes those arguments in all five 8723DU and 8821CU load commands. The script checks the exact source hash, command counts, output length, and changed-byte count. See [the custom firmware status](research/custom-firmware-status.md).
- Found a boot hook in the extracted firmware: `/opt/nwsoc_data/ExtBoot`, executed before `nwsoc`. No verified network method to write this hook has been found.
- Traced the updater's network POST selection and generic SHA-256/ECDSA P-256 verification code. The ET-3850 RCX signature verifies against an embedded public key, but the updater's compiled key table omits XB20 and its model-specific path is unresolved. A modified RCX is not currently installable. See [the updater signature trace](research/updater-signature.md).
- Mapped printer-side firmware update GET and POST route-table entries on ports 80 and 443. Under a protection flag, port 80 rejects these routes and HTTPS requires Basic administrator credentials. The POST path crosses the D4 controller-facing IPC channel; its controller handler and signature gate remain unidentified. One zero-byte live POST returned HTTP 500 and was followed by a brief loss of network status, then recovery; no payload was sent. See [the network update route trace](research/network-update-route-trace.md).
- Traced a second boot-image key copy descriptor and the P-256 verification decision. The `EPSONSIGN` parser reads a runtime copy of the same public key embedded in both RCX releases. What authenticates the boot image itself remains unresolved. See [the updater signature trace](research/updater-signature.md).
- Rebuilt the second SquashFS with the patched `nwsoc`, placed it inside a same-length offline RCX, and made both IPL key copies and the outer signature internally consistent with an ephemeral key. Re-extraction recovered the patched executable byte-for-byte. A check against the existing XB22Q5 IPL key **rejects** this self-signed candidate. It has not been sent to the printer. See [the custom firmware status](research/custom-firmware-status.md).
- Built a second offline candidate combining the patched executable with a suspend script that keeps the USB Wi-Fi device awake. Both files re-extract from its RCX with the expected hashes, and the combined image fits the original SquashFS slot. The current IPL key rejects it; no upload or print has occurred.
- Confirmed the live printer advertises JPEG printing over IPPS. A cake page generator and explicit-send IPPS client are ready for the final print, after a custom change is installed and verified. The IPPS client was exercised in read-only mode only.
- Reproduced Epson's already disclosed SNMP/default-password issue on the test printer, without storing its serial or password. Traced the certificate import handler; no arbitrary file write was established.
- Traced a possible ENPC hostname-to-DHCP shell path. The authenticated network configuration session and same-value write work on the live printer. The configuration-scope transition and command execution remain unverified. See [ENPC/DHCP lead](research/enpc-dhcp-lead.md).
- Found an ENPC-readable `WLAN_POWER_MANAGEMENT_MODE` setting. The live value is `1`, which the IEEE 802.11 MIB defines as active mode for its similarly named attribute. No write was made, and no link to the Realtek USB autosuspend flags has been shown. See [WLAN power setting](research/wlan-power-setting.md).
- Reproduced an unchecked `ip neigh` address copy in an isolated ARM run of the actual parser: a 38-character IPv6 token overwrote the guard after a 16-byte buffer. The wireless peer prerequisites and device impact are unverified. See [the memory safety finding](research/ip-neigh-buffer-lead.md).
- Traced the setup restore archive parser. It passes record filenames to `open()` with truncate flags after a CRC32 check, but the data currently comes through a controller event and no LAN injection path has been shown. See [setup restore parser](research/setup-restore-parser.md).
- Decoded a CROM image inside the first IPL with an independent decoder. It contains controller code for `SetupData:`, `ReadSetup`, and `WriteSetup`. The traced direct `SetupData:` producer has an `IPPRes:` prefix that fails its own base64-only event check, so it is not a demonstrated LAN route. See [controller CROM trace](research/controller-crom-trace.md) and [hash-checked extractor](scripts/extract_controller_crom.py).
- Ran the controller's setup gate in isolated ARM emulation: `IPPRes:` and 31-character inputs are rejected; 32 base64 characters reach the internal request call. The [emulator script](scripts/emulate_setup_gate.py) uses the separately extracted image and does not contact the printer.
- Checked the controller's internal request dispatcher: the `0x41` and `0x42` entries in this image branch back to its wait loop, including the command used by `SetupData:`. The [jump-table check](scripts/inspect_controller_event_routes.py) reproduces the static targets. This path is not a verified network update channel.
- Confirmed a read-only Epson Remote Mode status command over the printer's private SNMP OID subtree. This shows a network controller command tunnel, but no setup restore command through it. The [status probe](scripts/probe_remote_status.py) prints only response metadata.
- Surveyed the extracted program's process launchers. A console thread can run shell commands from its input, while the Wi-Fi suspend script arguments come from `/dev/usb-detector`; neither has a demonstrated LAN input route. See [process-launch survey](research/process-launch-survey.md).
- Traced LPR port 515 control records and the immediate data-file-name helpers. The supplied filename becomes print submission metadata in the inspected path; no direct Linux file write was found there. See [LPR input trace](research/lpd-input-trace.md).

See [firmware layout](research/firmware-layout.md), [network surface](research/network-surface.md), [administrator API and URL inventory](research/admin-api-inventory.md), and [vulnerability notes](research/vulnerabilities.md).

The Device Admin installer lead is recorded in [earlier notes](research/device-admin-lead.md) but is not the current route. Current work follows the firmware's own network transport and boot verification code.

For a read-only ENPC UDP 3289 reachability check:

```powershell
python scripts/probe_enpc_readonly.py PRINTER_IP
```

This `N` request only produces a status reply; it cannot determine whether ENPC configuration writes are authenticated.

To inspect endpoint-shaped strings in local copies of the extracted ARM program and Windows updater without contacting the printer:

```powershell
python scripts/inventory_endpoints.py path/to/nwsoc path/to/EPFWUPD.exe
python scripts/inspect_network_update_routes.py path/to/nwsoc
```

The script prints file offsets. For this `nwsoc` Ghidra project, virtual addresses are file offsets plus `0x10000`.

To check the signed segment layout of a separately obtained RCX without sending data to the printer:

```powershell
python scripts/inspect_signature_block.py path/to/FWCJ61TL.rcx
```

For a cryptographic consistency check using the public key embedded in this XB22Q5 RCX, install Python's `cryptography` package and run `python scripts/verify_rcx_signature.py path/to/FWCJ61TL.rcx`. This embedded-key check alone does not prove that the printer trusts or rejects the image.

With the matching `EPFWUPD.exe` from the same recovery download, run `python scripts/check_updater_key_table.py path/to/EPFWUPD.exe path/to/FWCJ61TL.rcx` to reproduce the generic key-table comparison.

To compare two separately obtained official RCX files, run `python scripts/compare_official_releases.py path/to/older.rcx path/to/newer.rcx`.

## Reproduce offline extraction

Get the official recovery package from [Epson's ET-3850 support page](https://epson.com/Support/Printers/All-In-Ones/ET-Series/Epson-ET-3850/s/SPT_C11CJ61201). Then run:

```powershell
python scripts/extract_official.py --package FWCJ61TL_XB22Q5.exe --output data
```

The script checks the package and RCX SHA-256 hashes, extracts the nested RCX, and carves two SquashFS images. Use `unsquashfs` to inspect them. To create the candidate binary from the second image's `/opt/nwsoc/nwsoc`:

```powershell
python scripts/patch_candidate.py --input path/to/nwsoc --output path/to/nwsoc.patched
python scripts/patch_suspend_candidate.py --input path/to/wlan_enable_suspend.sh --output path/to/wlan_enable_suspend.sh.patched
python scripts/patch_wifi_power_all.py --input path/to/nwsoc --output path/to/nwsoc.wifi-power-all
scripts/repack_wifi_candidate.sh path/to/squashfs_1.img path/to/nwsoc.wifi-power-all path/to/repacked.img
scripts/repack_wifi_candidate.sh path/to/squashfs_1.img path/to/nwsoc.wifi-power-all path/to/repacked-combined.img path/to/wlan_enable_suspend.sh.patched
python scripts/build_self_signed_control.py --input path/to/FWCJ61TL.rcx --squashfs path/to/repacked.img --output path/to/offline-control.rcx
```

The suspend-script candidate keeps USB `power/control` at `on` and blocks Realtek autosuspend when the firmware calls the enable-suspend script. That call appears in a USB/Bluetooth initialization path; whether the script influences the reported Wi-Fi fault is unknown. All candidates are offline research artifacts. There is no install command in this repository. The repack script requires Linux `unsquashfs` and `mksquashfs` and leaves its temporary extraction path for inspection.

## Reporting

The [vulnerability notes](research/vulnerabilities.md) distinguish known Epson advisories from research leads. This repository currently contains **no new confirmed vulnerability** and no submission to Epson. A report will require a reproducible, device-specific security impact and a minimal proof that does not expose printer credentials.

The [disclosure template](research/disclosure-template.md) is ready if a new finding is confirmed.
