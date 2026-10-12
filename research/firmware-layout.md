# XB22Q5 firmware layout and boot path

The official `FWCJ61TL_XB22Q5.exe` is a self-extracting ZIP containing `FWCJ61TL.efu`. The EFU is another ZIP containing `FWCJ61TL.rcx`. The RCX is 40,608,018 bytes and contains two SquashFS images at offsets `0xEA7112` and `0x1197112`.

The first filesystem has Linux 4.4.27 boot scripts and kernel modules. The second has `/opt/nwsoc/nwsoc`, an ARM EABI/uClibc network application, plus the Realtek Wi-Fi driver `8723du.ko` and its firmware blob.

The extracted boot path is:

1. `/root/PreBoot` runs `/etc/init.d/S00fsmount`, which mounts JFFS2 `/dev/mtdblock4` at `/opt/nwsoc_data`.
2. `PreBoot` runs `/etc/init.d/S01debug`, which executes `/opt/nwsoc_data/ExtBoot` if present.
3. `PreBoot` runs `/etc/init.d/S99NWControl`, which starts `/opt/nwsoc/NWControl` and then `nwsoc`.

This is a possible location for a persistent modification **if** a network write path can be established. The hook is not itself a remote write mechanism. The writable partition size and recovery behavior have not been measured.

The `nwsoc` binary contains an `insmod` command for `8723du.ko` with `rtw_power_mgnt=1 rtw_enusbss=1`. The candidate changes those two ASCII digits to `0`. It is byte-length preserving and SHA-guarded by the script in this repository, but it has not reached Wi-Fi initialization in emulation.

The binary also invokes `/opt/nwsoc/wlan_enable_suspend.sh` and `/opt/nwsoc/wlan_disable_suspend.sh`. The enable script sets USB `power/control` to `auto` and clears the Realtek `auto_suspend_block` flag; the disable script sets `power/control` to `on` and sets that flag. This means the two-digit module argument patch alone might not keep USB autosuspend disabled. The candidate remains a hypothesis until the actual call conditions and Wi-Fi behavior can be tested.

## Hashes

| Artifact | SHA-256 |
| --- | --- |
| Official recovery EXE | `e12cb391e4473391115d6e4c5d8dc3c9bd1e3ca78727a5cbb79370947a50d731` |
| Extracted RCX | `103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675` |
| Original `nwsoc` | `70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0` |
| Candidate `nwsoc` | `5136c1deeeac519fe3dbcde7e094f7012768fa454e3954a9056313ab6a3a4652` |
