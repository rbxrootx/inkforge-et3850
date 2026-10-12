# ENPC hostname to DHCP shell: static research lead

The XB22Q5 `nwsoc` binary contains a potential command injection chain. This is **not a confirmed vulnerability** or an installation method. No configuration write packet has been sent to the live printer. A single read-only `N` request received a 14-byte `EPSONn` reply from UDP 3289.

## Observed code path

1. `nwsoc` binds a UDP socket to network byte order `0x0cd9` (port 3289). Its parser expects the five-byte `EPSON` prefix. The packet dispatcher at `0x1babd0` routes `I` command `0x18` to `0x1bf8b0`, and the `S` command family has a similar writer at `0x1be950`.
2. The writers use `0x1c6cc8` to measure a bounded string. That helper counts bytes up to a NUL or limit; it does not restrict shell metacharacters. The writers pass packet bytes to the generic configuration setter for `IP_HOST_NAME` and `IP_DOMAIN_NAME`. They check length and some packet, interface, and mode conditions. The `I` handler can require a matching MAC/interface state. The dispatcher also consults `PS_PCD_SECURITY_FLAG` and `ENPC_ENCRYPTION_MODE`; the live values and effective authentication requirement are unknown.
3. Separately, `0x1a0908` reads `IP_HOST_NAME` from the `IP_CURRENT` scope and uses it in a `startup_dhcp.sh` command string passed to a `/bin/sh -c` wrapper. The local configuration routine at `0x19ef70` validates hostname characters before writing them. The ENPC writer's own branch shows length checks rather than that character validation.

## Missing link

The ENPC writer stores `IP_HOST_NAME` under the `IP` scope. The DHCP launcher reads `IP_CURRENT`. The code that copies or applies a value between those scopes, and the conditions that trigger the DHCP launcher, must be verified. It is also necessary to determine whether packet security blocks the path on the ET-3850 and whether another layer validates the value. A shell character in a stored field is not proof of code execution by itself.

## Safe next verification

Decode a read-only ENPC response to identify protocol mode and current configuration behavior. Then reproduce the scope transition and command construction in an offline harness. A live proof should use a reversible, non-persistent marker with an observed response, preserve the original network settings, and avoid placing the printer out of reach. Only after a reproducible security impact should this be promoted to a disclosure report.
