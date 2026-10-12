# Process-launch survey of XB22Q5 `nwsoc`

This is an offline call-site survey of the extracted ARM program. It identifies places where network-controlled data would need to reach a shell or process launcher; it does not demonstrate a network command-execution route.

`FUN_000a40b0` (`0x000a40b0`) invokes `/bin/sh sh -c` with its string argument. Its direct caller `FUN_000a4d78` (`0x000a4d78`) is a wrapper used at roughly thirty call sites. Many pass constant command strings. The following variable call sites merited closer inspection:

| Call site | Source seen in this image | Result |
| --- | --- | --- |
| `0x00271d8c` | Formats `/opt/nwsoc/wlan_enable_suspend.sh %d %s`; the `%s` comes from an ioctl on `/dev/usb-detector`. | No LAN source established. This is relevant to the proposed Wi-Fi suspend change, but it does not provide a network write foothold. |
| `0x00271f8c` | Formats `/opt/nwsoc/wlan_disable_suspend.sh %s`; the `%s` also comes from `/dev/usb-detector`. | No LAN source established. |
| `0x001a0908` | Formats `./startup_dhcp.sh %s %d %s %s %s %s %s%s` from configuration and local state. | The hostname argument is the existing [ENPC/DHCP research lead](enpc-dhcp-lead.md); live probes have not shown that a shell expression can be stored. |
| `0x000a0ab8` | Reads a line with `fgets` and passes it to the wrapper. `0x000a0954` starts this as a `Console` thread; the surrounding menu prints `enter shell command:`. | A built-in console command facility exists, but no network transport to its input was identified. |
| `0x002c3ec4` | Accepts a command string and retries the shell wrapper. | No direct code reference to this helper was found in the analyzed image. |

Separately, `FUN_00330158` forks and calls `execv(param_1, argv)` after splitting a supplied argument string. Ghidra found no direct code or data reference to the function entry. A potentially useful primitive in the binary is not a reachable primitive without a caller and controllable input.

The survey does not prove these are the only execution paths. It covers direct `system`, `popen`, `execl`, `execv`, and calls to the identified shell wrapper in this image; indirect calls and code outside this extracted program remain open. No custom firmware was installed and no printer command was sent during this survey.
