# XB05O7 versus XB22Q5 Wi-Fi components

Two official ET-3850 recovery packages were obtained from Epson's public download server: `FWCJ61TL_XB05O7.exe` and `FWCJ61TL_XB22Q5.exe`. Their RCX images have the same size, signature marker, and embedded P-256 public key. Both signatures verify against that embedded key. See [the signature trace](updater-signature.md) for the hashes and trust limitation.

Both images place SquashFS filesystems at RCX offsets `0xEA7112` and `0x1197112`. Extracting them produced the following comparison:

| Component | XB05O7 | XB22Q5 | Observation |
| --- | --- | --- | --- |
| `nwsoc` ARM application | SHA-256 `fb4615143f2b7c40c0eac261d5b60d22875ceca2473ea973cbe72c7f6ce53fa1` | SHA-256 `70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0` | Different binary, same 480 extracted strings matching Wi-Fi, WLAN, Realtek, 802.11, power, or suspend terms. |
| `wlan_enable_suspend.sh` | SHA-256 `dd63b11cade9a72a570e9fe28d680456b5dfed51530a34d25f28acd55e93322a` | Same | Byte-identical. |
| `wlan_disable_suspend.sh` | SHA-256 `8e0705f4865bc756251badc69db61871579dbc1fbdcb5f40fa8c0b42c83b364a` | Same | Byte-identical. |
| Realtek `rtl8723du_fw` blob | SHA-256 `2c984871d8ef00b5e54005425b35aa55d68316b6c2870626282c51f49c6d5f20` | Same | Byte-identical. |
| `8723du.ko` kernel module | 1,440,388 bytes; SHA-256 `02f71d14ce784a6fcd1ddaf626531a1971f660354fc91f25f7a526d785c593ff` | 1,441,936 bytes; SHA-256 `261da3aadf20428c814ec75c9efe671058623dc066857ee5552afed51ddb6418` | Different builds, both advertise `1930.16.1213.2016_BETA_V23.3` and Linux `4.4.27` vermagic. |

In both `nwsoc` binaries, the five `insmod` command strings for the 8723DU and 8821CU variants still use `rtw_power_mgnt=1 rtw_enusbss=1`. The newer `8723du.ko` contains `CONFIG_FIX_NR_BULKIN_BUFFER` and association-response handler strings absent from the older one. Its build-path strings indicate April 2025, compared with August 2023 in the older module. These are *build artifacts and leads*, not proof of a specific Wi-Fi fix. The live printer already reports XB22Q5, so installing XB05O7 would not test a newer fix.

HTTP/API-shaped strings extracted from old and new `nwsoc` are identical as sets (526 matching strings in each). No newly named administrative upload route appears in this comparison. A binary comparison of strings cannot rule out changed behavior behind an existing route.

This comparison does not reproduce the reported Wi-Fi failure, establish the live unit's radio variant, or show an install path for a custom RCX.
