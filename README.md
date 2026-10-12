# Epson ET-3850 firmware research

Private owner research and modding workbench for the ET-3850. This repository is hosted in a private GitHub repository. It contains build and install code but no Epson firmware, device credentials, or flashable image. Keep the installation path private while the updater finding is prepared for disclosure.

**InkForge private mod:** Run `python et3850_mod.py gui` for a retro UI with a complete offline firmware build, checked USB installer, and root command deck. The pinned stock RCX and generated password stay in local `work/`. See [the current workflow](research/inkforge-private.md). The public [companion repo](https://github.com/rbxrootx/et3850-mod-lab) does not contain the installer or bypass.

**Live result (2026-10-12):** A custom image ran on the owner's physical ET-3850. A private TCP 2323 login returned `uid=0(root)`; the running network executable matched our patched digest; and the Realtek driver reported `rtw_power_mgnt=0` and `rtw_enusbss=0`. The Python USB sender and companion shell client work. The package was **not** signed with Epson's private key. The exact live acceptance path, long-term Wi-Fi benefit, SSH, and personal-photo home wallpaper remain unresolved. See [live install verification](research/live-custom-install.md). Older sections below preserve the investigation as it developed and may describe earlier candidate states.

## Custom Python jailbreak workbench

Run `python et3850_mod.py` from this directory to open the retro graphical client. It has live Windows USB and print-queue discovery, an ET-3850 USBPRINT D4 version/status query, offline RCX inspection, a hash-locked Wi-Fi/Telnet candidate builder, an explicit-address SSH/Telnet reachability check, and LCD theme previews. `Pillow` is needed for the preview and `cryptography` for embedded-key signature verification; the USB transport itself uses the Python standard library. The client is our code and does not execute Epson's updater.

The builder uses files in local `work/`: the pinned XB22Q5 RCX and rebuilt first and second SquashFS images. Its output also stays in `work/`, outside this Git repository. The default GUI paths match this investigation's local layout. The command-line forms are:

```powershell
python et3850_mod.py status
python et3850_mod.py usb-status
python et3850_mod.py inspect ..\..\work\FWCJ61TL.rcx
python et3850_mod.py build ..\..\work\FWCJ61TL.rcx ..\..\work\telnet_squashfs_1.img ..\..\work\telnet_wifi_candidate.rcx --first-squashfs ..\..\work\telnet_squashfs_0.img
python et3850_mod.py flash ..\..\work\telnet_wifi_photo_candidate.rcx
python et3850_mod.py services PRINTER_IP
```

The `flash` command shown above is preflight only unless `--send` is supplied. The corrected USBPRINT sender transferred both signed stock and a custom image and received `fl:03:OK`. The custom image was verified running on this printer by its startup marker, password-gated root shell, executable digest, and Wi-Fi driver parameters. WinUSB accepts control commands but rejected the DATA socket before receiving image bytes. Normal signature verification rejects the custom image, and the exact live controller decision path has not been observed. The photo was placed in a blue-wave resource, but the owner reports a white home screen with blue tiles and only solid-color wallpaper choices, so that resource is not the observed active home background. See [USB route](research/usb-update-route.md), [photo wallpaper](research/photo-wallpaper.md), and [Telnet unlock path](research/telnet-unlock.md).

## Current state

- Extracted Epson's official XB22Q5 recovery package. The live printer reports `05.15.XB22Q5`.
- The owner connected the ET-3850 by USB. Windows sees composite `VID_04B8&PID_1181`. Our own Python client opened USBPRINT `MI_01`, negotiated IEEE 1284.4 D4, read `vi`/`st` from `EPSON-CTRL`, and opened `EPSON-DATA` with MTU 32768. Keeping CTRL open during DATA allowed a complete signed-stock upload and update-end acknowledgement. WinUSB `MI_02` answers D4 control but rejects `EPSON-DATA`; see [local update trace](research/usb-update-route.md).
- Re-encoded the owner's photo as an exact-size 320x240 PNG inside the UI CROM, then merged that verified CROM into a local Wi-Fi/Telnet candidate. The complete decoded UI image differs only at the wallpaper PNG, and all three RCX record integrity checks pass. Normal signature verification still rejects the offline image; see [photo wallpaper](research/photo-wallpaper.md).
- Located the owner's 320×240 blue LCD wave background in a decoded controller CROM. A violet/cyan palette change was patched into the compressed CROM and verified offline: re-decoding changes only that PNG. A richer demoscene-style preview is prepared, but its full image replacement and installation remain unverified. See [LCD background assets](research/lcd-background.md).
- Compared an older official XB05O7 package with XB22Q5. The embedded signing key, suspend scripts, Realtek firmware blob, Wi-Fi module arguments, and HTTP/API-shaped string set are stable; the 8723DU kernel module changed. See [the release comparison](research/official-release-comparison.md).
- Rehosted the ARM `nwsoc` application under QEMU with synthetic controller replies. Both the original and patched binaries reach D4 communication, PCIF, and SNMP initialization. An offline-only WebApp shim also opens HTTP listeners on ports 80 and 443 inside an isolated network namespace. The mock does not supply the USB detector or valid later D4 events, so the Realtek driver command has not run. See [the application rehost trace](research/application-rehost.md).
- Identified a candidate change to the Realtek 8723DU module arguments: `rtw_power_mgnt=1 rtw_enusbss=1` to `0,0`. **This has not been validated as a fix.** The executable has 8821CU loader strings, but direct SquashFS listings contain only the 8723DU module and firmware. The test printer's actual USB product identifier is unknown.
- Built a second offline candidate that changes those arguments in all five 8723DU and 8821CU load commands. The script checks the exact source hash, command counts, output length, and changed-byte count. See [the custom firmware status](research/custom-firmware-status.md).
- Found a boot hook in the extracted firmware: `/opt/nwsoc_data/ExtBoot`, executed before `nwsoc`. No verified network method to write this hook has been found.
- Traced the updater's network POST selection and generic SHA-256/ECDSA P-256 verification code. The ET-3850 RCX signature verifies against an embedded public key, but the updater's compiled key table omits XB20 and its model-specific path is unresolved. A modified RCX has been transferred over USB; installation remains unverified. See [the updater signature trace](research/updater-signature.md).
- Mapped printer-side firmware update GET and POST route-table entries on ports 80 and 443. Under a protection flag, port 80 rejects these routes and HTTPS requires Basic administrator credentials. The generic POST path crosses the D4 controller-facing IPC channel. A corrected controller CROM mapping identifies preparation, `GetRequestID`, ROM1 selection, channel-1 body read, and the signed package reader in static code. A 20-byte invalid-marker POST alone returned 500 without an uptime reset, while a preparation GET followed by the same POST returned 500 and coincided with an SNMP uptime reset. A GET-only control kept uptime rising. No firmware image was sent. See [the network update route trace](research/network-update-route-trace.md).
- The user later observed “Preparing for firmware update” with a loading circle and `Cancel` on the physical screen, without starting an update from the panel. `Cancel` returned it to the normal screen; a later read-only version query still returned `XB22Q5`. Earlier preparation requests may have caused the screen, but the trigger and start time are unproved. No image was sent. See [the live observation](research/network-update-route-trace.md).
- A broader [hash-checked HTTP route scan](scripts/inventory_http_route_table.py) found 46 route records. The [generic `/DOWN/` trace](research/generic-down-stream.md) follows a conditional body stream into D4 controller IPC. A harmless 19-byte marker reached the mock controller channel and received HTTP 200 after two controller success replies and a matching nonzero D4 request ID were fabricated in isolated QEMU. The fabricated reply now matches the decoded controller callback's `ChID:1` and nonzero-ID requirement. Real controller acceptance and any ability to install remain unresolved.
- Traced a second boot-image key copy descriptor and the P-256 verification decision. The `EPSONSIGN` parser reads a runtime copy of the same public key embedded in both RCX releases. What authenticates the boot image itself remains unresolved. See [the updater signature trace](research/updater-signature.md).
- Rebuilt the second SquashFS with the patched `nwsoc`, placed it inside a same-length offline RCX, and made both IPL key copies and the outer signature internally consistent with an ephemeral key. Re-extraction recovered the patched executable byte-for-byte. A check against the existing XB22Q5 IPL key **rejects** this self-signed candidate. It has not been sent to the printer. See [the custom firmware status](research/custom-firmware-status.md).
- Built a second offline candidate combining the patched executable with a suspend script that keeps the USB Wi-Fi device awake. Both files re-extract from its RCX with the expected hashes, and the combined image fits the original SquashFS slot. The current IPL key rejects it; no upload or print has occurred.
- Confirmed the live printer advertises JPEG printing over IPPS. A cake page generator and explicit-send IPPS client are ready for the final print, after a custom change is installed and verified. The IPPS client was exercised in read-only mode only.
- Reproduced Epson's already disclosed SNMP/default-password issue on the test printer, without storing its serial or password. Traced the certificate import handler; no arbitrary file write was established.
- Traced the hidden ENUP raw-IP maintenance channel and its RSA challenge. After authentication, its command handlers expose Telnet and GDB triggers, terminal output redirection, and NFS configuration fields. No bypass was found. The [offline checker](scripts/inspect_enup_auth.py) and [debug-channel trace](research/enup-debug-channel.md) record its exact constants and packet-length audit leads.
- Traced a possible ENPC hostname-to-DHCP shell path. The authenticated network configuration session and same-value write work on the live printer. The configuration-scope transition and command execution remain unverified. See [ENPC/DHCP lead](research/enpc-dhcp-lead.md).
- Found an ENPC-readable `WLAN_POWER_MANAGEMENT_MODE` setting. The live value is `1`, which the IEEE 802.11 MIB defines as active mode for its similarly named attribute. No write was made, and no link to the Realtek USB autosuspend flags has been shown. See [WLAN power setting](research/wlan-power-setting.md).
- Reproduced an unchecked `ip neigh` address copy in an isolated ARM run of the actual parser: a 38-character IPv6 token overwrote the guard after a 16-byte buffer. The wireless peer prerequisites and device impact are unverified. See [the memory safety finding](research/ip-neigh-buffer-lead.md).
- Traced the setup restore archive parser. It passes record filenames to `open()` with truncate flags after a CRC32 check. Controller queue `0x6e` event `7` selects the internal `readsetup`/`writesetup` command. The outer `||` dispatcher responds through public SNMP, but a no-change `p` probe returned `NA`; accepted archive bytes have not been shown. See [setup restore parser](research/setup-restore-parser.md), [setup command event chain](research/setup-command-event-chain.md), and [remote setup dispatch](research/remote-setup-dispatch.md).
- The first IPL's copied RAM initialization block sets the `||` setup gate at `0x43edb930` to zero. If the SNMP callback supplies source argument `4`, this blocks the inner setup command until some other state transition sets it to `1`. The live state and writer are still unknown; the [hash-locked inspector](scripts/inspect_setup_event7.py) checks the initial value.
- Enumerated the controller's 15 remote command handlers. A read-only `vi` query returned `XB22Q5` through the public SNMP tunnel. The [remote command inventory](research/remote-command-inventory.md) distinguishes static handlers from live responses; none provides a verified install path.
- Decoded a CROM image inside the first IPL. Its actual load base is `0x4566ff74`, 0x8c below the original Ghidra mapping. The corrected request table maps `EpsonLocalReq:GetRequestID` to a `Method:`/`URI:` parser. A first-IPL copy descriptor recovers the RAM callback table and links ROM1 selection to the package source, channel-1 read, and signed reader. This is a static route, with no captured live accepted image. The separate `SetupData:` producer has an `IPPRes:` prefix that fails its base64 gate. See [controller CROM trace](research/controller-crom-trace.md), [extractor](scripts/extract_controller_crom.py), and [update-chain checker](scripts/inspect_controller_update_chain.py).
- Traced the signed reader's success through ROM1 completion status and both callbacks to a handoff of three staged-record descriptors through external commands `0x2a` and `0x2b`. The receiving component's validation and flash action remain unknown. See the [controller CROM trace](research/controller-crom-trace.md).
- Audited the unresolved external targets against both XB22Q5 and older XB05O7 scanner CROM images. A direct remap to `0x4370d000` is unlikely: both target offsets land inside existing functions, and neither image has internal string-pointer anchors at that base. The generic `/UP/` table contains print-service routes, not a firmware readback route. See the [external handoff gap](research/external-handoff-gap.md).
- Confirmed that a separate scanner CROM has memory-dump and memory-edit debug commands, then traced its input to a memory-mapped register and a scanner maintenance-mode event. No network entry point to that console has been found. See the [scanner debug-console trace](research/scanner-debug-console.md).
- The `EPSONSIGNXB20d` package reader in that decoded controller image uses a P-256 verification key loaded from the **running** first IPL, not from the incoming RCX. The [key-source checker](scripts/inspect_controller_signature_gate.py) reproduces this from the decoded image and IPL. The self-signed Wi-Fi candidate fails against that key offline; live controller acceptance and any earlier authentication gate remain unresolved.
- Found a [controller signed-stream length bypass](research/controller-signature-length-bypass.md) in the decoded image. The actual ARM reader returns success without calling ECDSA when the unsigned payload length is one byte larger than the three package records it consumes. An offline Wi-Fi candidate with recalculated record sums, SHA-1 digests, and one trailing byte reproduces this control flow. The candidate's signature fails against the current IPL key. The static ROM1 route now reaches this reader, but no successful live upload or installation is established.
- Built a second offline length-bypass control with a four-byte patch to the candidate first IPL's conditional finalizer branch. The decoded controller reader and the patched IPL branch both skip their local rejection calls in isolated ARM runs. Boot-ROM authentication and whether the modified IPL is installed or executed remain unknown; this control was not uploaded. See the [candidate builder](scripts/build_length_gate_candidate.py) and [IPL branch emulator](scripts/emulate_ipl0_finalizer_branch.py).
- Traced the first IPL's mode-`2` verification gate to a startup byte at `0x82c00000`. Its stock `XB22Q5` marker matches the built-in `XB` family check. A recovered first-IPL callback table points to the signature finalizer, and an early boot branch conditionally enters the update routine that invokes it. The live boot mode and update-path ordering remain unknown. The [boot-mode checker](scripts/inspect_ipl0_boot_mode.py) and [dispatch checker](scripts/inspect_ipl0_update_dispatch.py) reproduce the static evidence.
- Re-ran the controller's group `0x76` dispatch at the corrected load base. Subcommand `8` enters the ROM selector. The earlier low-address-write finding was a mapping artifact and is [retracted](research/controller-event-table-memory-safety.md).
- Ran the controller's setup gate in isolated ARM emulation: `IPPRes:` and 31-character inputs are rejected; 32 base64 characters reach the internal request call. The [emulator script](scripts/emulate_setup_gate.py) uses the separately extracted image and does not contact the printer.
- Checked the controller's internal request dispatcher at the corrected load base: entries `0x41` and `0x42` are valid branch targets. The earlier loop-back interpretation was a mapping error. The [jump-table check](scripts/inspect_controller_event_routes.py) reproduces the static targets; the `SetupData:` route remains unproved as a network update channel.
- Confirmed a read-only Epson Remote Mode status command over the printer's private SNMP OID subtree. This shows a network controller command tunnel, but no setup restore command through it. The [status probe](scripts/probe_remote_status.py) prints only response metadata.
- Surveyed the extracted program's process launchers. A console thread can run shell commands from its input, while the Wi-Fi suspend script arguments come from `/dev/usb-detector`; neither has a demonstrated LAN input route. See [process-launch survey](research/process-launch-survey.md).
- Traced LPR port 515 control records and the immediate data-file-name helpers. The supplied filename becomes print submission metadata in the inspected path; no direct Linux file write was found there. See [LPR input trace](research/lpd-input-trace.md).

See [firmware layout](research/firmware-layout.md), [network surface](research/network-surface.md), [administrator API and URL inventory](research/admin-api-inventory.md), and [vulnerability notes](research/vulnerabilities.md).

The Device Admin installer lead is recorded in [earlier notes](research/device-admin-lead.md) only as historical context. The user has excluded Epson's official admin and updater tools. Current work follows the firmware's network and USB transports and boot verification code with a self-built client.

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

The suspend-script candidate keeps USB `power/control` at `on` and blocks Realtek autosuspend when the firmware calls the enable-suspend script. That call appears in a USB/Bluetooth initialization path; whether the script influences the reported Wi-Fi fault is unknown. All custom candidates remain offline research artifacts. The experimental USB sender completed an acknowledged signed-stock transfer, but custom-image acceptance remains unknown. The repack script requires Linux `unsquashfs` and `mksquashfs` and leaves its temporary extraction path for inspection.

## Reporting

The [vulnerability notes](research/vulnerabilities.md) distinguish known Epson advisories from research leads. A custom image was installed on the owner's physical ET-3850, establishing live impact for the firmware acceptance issue, while the exact decision path remains unobserved. No submission to Epson has been sent. The private controller length-bypass analysis is ready for vendor triage.

The [disclosure template](research/disclosure-template.md) is ready if a new finding is confirmed.
