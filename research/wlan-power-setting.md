# WLAN power-mode network setting

The XB22Q5 `nwsoc` binary has a `WLAN_POWER_MANAGEMENT_MODE` configuration key. Its ENPC `I/0x96` read handler at `0x1b8338` places that value at response offset `0x14`. The `I/0x96` write handler at `0x1c3700` can store a byte from the same offset when its configuration-session checks pass and `WLAN_POWER_MANAGEMENT_MODE_SUPPORT` equals `1`. These are firmware code paths, not evidence that a value change fixes USB Wi-Fi suspend behavior.

A [read-only probe](../scripts/probe_enpc_wlan_power.py) of the local ET-3850 returned a 39-byte `I/0x96` response, status `0x1000` (outside a write session), and power-mode byte `1`. No setting was changed. A separate read attempt for the support page (`I/0x90`) returned a 14-byte `0xffff` response, so the live support flag remains unknown.

The [IEEE 802.11 MIB](https://www.ieee802.org/11/MIB/802.11-2020mib.txt) defines `dot11PowerManagementMode` value `1` as **active** and `2` as **power save**. Epson's similarly named key might follow that convention, but this has not been proved by tracing it to the Realtek driver. If it does, the observed `1` already denotes active 802.11 mode. The hardcoded Realtek loader still uses `rtw_power_mgnt=1 rtw_enusbss=1`; the ENPC key is not passed to that loader in the direct references found so far.

This setting is therefore an additional control surface to study, not a validated firmware-install method or Wi-Fi fix. Do not change it to `0` on the assumption that zero means power saving disabled. No ENPC write, printer restart, or cake print occurred in this check.
