# Epson ET-3850 firmware research

Research into the ET-3850 network firmware and a possible Wi-Fi power-management modification. This repository contains original analysis and tools only. It does not distribute Epson firmware, device credentials, or a flashable image.

## Current state

- Extracted Epson's official XB22Q5 recovery package. The live printer reports `05.15.XB22Q5`.
- Rehosted the ARM `nwsoc` application under QEMU. It reaches the internal EPIDC/D4 controller handshake, then stops before Wi-Fi initialization.
- Identified a candidate change to the Realtek 8723DU module arguments: `rtw_power_mgnt=1 rtw_enusbss=1` to `0,0`. **This has not been validated as a fix.**
- Found a boot hook in the extracted firmware: `/opt/nwsoc_data/ExtBoot`, executed before `nwsoc`. No verified network method to write this hook has been found.
- Confirmed that the official updater binary contains a network transport and host-side firmware signature verification. A modified RCX is not currently installable.
- Reproduced Epson's already disclosed SNMP/default-password issue on the test printer, without storing its serial or password. Traced the certificate import handler; no arbitrary file write was established.
- Traced a possible ENPC hostname-to-DHCP shell path. The packet writer and shell sink are present, but the configuration-scope transition and live security gate remain unverified. See [ENPC/DHCP lead](research/enpc-dhcp-lead.md).

See [firmware layout](research/firmware-layout.md), [network surface](research/network-surface.md), and [vulnerability notes](research/vulnerabilities.md).

For a read-only ENPC UDP 3289 reachability check:

```powershell
python scripts/probe_enpc_readonly.py PRINTER_IP
```

This `N` request only produces a status reply; it cannot determine whether ENPC configuration writes are authenticated.

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

The second candidate keeps USB `power/control` at `on` and blocks Realtek autosuspend when the firmware calls the enable-suspend script. Both candidates are offline research artifacts. There is no install command in this repository.

## Reporting

The [vulnerability notes](research/vulnerabilities.md) distinguish known Epson advisories from research leads. This repository currently contains **no new confirmed vulnerability** and no submission to Epson. A report will require a reproducible, device-specific security impact and a minimal proof that does not expose printer credentials.

The [disclosure template](research/disclosure-template.md) is ready if a new finding is confirmed.
