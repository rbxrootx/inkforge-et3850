# Epson ET-3850 firmware research

Research into the ET-3850 network firmware and a possible Wi-Fi power-management modification. This repository contains original analysis and tools only. It does not distribute Epson firmware, device credentials, or a flashable image.

## Current state

- Extracted Epson's official XB22Q5 recovery package. The live printer reports `05.15.XB22Q5`.
- Rehosted the ARM `nwsoc` application under QEMU. It reaches the internal EPIDC/D4 controller handshake, then stops before Wi-Fi initialization.
- Identified a candidate change to the Realtek 8723DU module arguments: `rtw_power_mgnt=1 rtw_enusbss=1` to `0,0`. **This has not been validated as a fix.** The loader can also select an 8821CU driver, and the test printer's actual USB product identifier is unknown.
- Found a boot hook in the extracted firmware: `/opt/nwsoc_data/ExtBoot`, executed before `nwsoc`. No verified network method to write this hook has been found.
- Traced the updater's network POST selection and generic SHA-256/ECDSA P-256 verification code. The ET-3850 RCX signature verifies against an embedded public key, but the updater's compiled key table omits XB20 and its model-specific path is unresolved. A modified RCX is not currently installable. See [the updater signature trace](research/updater-signature.md).
- Reproduced Epson's already disclosed SNMP/default-password issue on the test printer, without storing its serial or password. Traced the certificate import handler; no arbitrary file write was established.
- Traced a possible ENPC hostname-to-DHCP shell path. The authenticated network configuration session and same-value write work on the live printer. The configuration-scope transition and command execution remain unverified. See [ENPC/DHCP lead](research/enpc-dhcp-lead.md).

See [firmware layout](research/firmware-layout.md), [network surface](research/network-surface.md), [administrator API and URL inventory](research/admin-api-inventory.md), and [vulnerability notes](research/vulnerabilities.md).

For a read-only ENPC UDP 3289 reachability check:

```powershell
python scripts/probe_enpc_readonly.py PRINTER_IP
```

This `N` request only produces a status reply; it cannot determine whether ENPC configuration writes are authenticated.

To inspect endpoint-shaped strings in local copies of the extracted ARM program and Windows updater without contacting the printer:

```powershell
python scripts/inventory_endpoints.py path/to/nwsoc path/to/EPFWUPD.exe
```

The script prints file offsets. For this `nwsoc` Ghidra project, virtual addresses are file offsets plus `0x10000`.

To check the signed segment layout of a separately obtained RCX without sending data to the printer:

```powershell
python scripts/inspect_signature_block.py path/to/FWCJ61TL.rcx
```

For a cryptographic consistency check using the public key embedded in this XB22Q5 RCX, install Python's `cryptography` package and run `python scripts/verify_rcx_signature.py path/to/FWCJ61TL.rcx`. This embedded-key check alone does not prove that the printer trusts or rejects the image.

With the matching `EPFWUPD.exe` from the same recovery download, run `python scripts/check_updater_key_table.py path/to/EPFWUPD.exe path/to/FWCJ61TL.rcx` to reproduce the generic key-table comparison.

## Reproduce offline extraction

Get the official recovery package from [Epson's ET-3850 support page](https://epson.com/Support/Printers/All-In-Ones/ET-Series/Epson-ET-3850/s/SPT_C11CJ61201). Then run:

```powershell
python scripts/extract_official.py --package FWCJ61TL_XB22Q5.exe --output data
```

The script checks the package and RCX SHA-256 hashes, extracts the nested RCX, and carves two SquashFS images. Use `unsquashfs` to inspect them. To create the candidate binary from the second image's `/opt/nwsoc/nwsoc`:

```powershell
python scripts/patch_candidate.py --input path/to/nwsoc --output path/to/nwsoc.patched
python scripts/patch_suspend_candidate.py --input path/to/wlan_enable_suspend.sh --output path/to/wlan_enable_suspend.sh.patched
```

The second candidate keeps USB `power/control` at `on` and blocks Realtek autosuspend when the firmware calls the enable-suspend script. That call appears in a USB/Bluetooth initialization path; whether the script influences the reported Wi-Fi fault is unknown. Both candidates are offline research artifacts. There is no install command in this repository.

## Reporting

The [vulnerability notes](research/vulnerabilities.md) distinguish known Epson advisories from research leads. This repository currently contains **no new confirmed vulnerability** and no submission to Epson. A report will require a reproducible, device-specific security impact and a minimal proof that does not expose printer credentials.

The [disclosure template](research/disclosure-template.md) is ready if a new finding is confirmed.
