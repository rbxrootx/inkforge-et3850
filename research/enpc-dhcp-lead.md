# ENPC hostname to DHCP shell: static research lead

The XB22Q5 `nwsoc` binary contains a potential command injection chain. This is **not a confirmed vulnerability** or an installation method. A read-only `N` request received a 14-byte `EPSONn` reply from UDP 3289. A same-value configuration write has also been accepted through a short-lived session authenticated with the existing Web Config administrator credential; readback showed the network fields were unchanged.

## Observed code path

1. `nwsoc` binds a UDP socket to network byte order `0x0cd9` (port 3289). Its parser expects the five-byte `EPSON` prefix. The packet dispatcher at `0x1babd0` routes `I` command `0x18` to `0x1bf8b0`, and the `S` command family has a similar writer at `0x1be950`.
2. The writers use `0x1c6cc8` to measure a bounded string. That helper counts bytes up to a NUL or limit; it does not itself restrict shell metacharacters. The writers pass packet bytes to the generic configuration setter for `IP_HOST_NAME` and `IP_DOMAIN_NAME`. Other validation can occur downstream. They check length and packet/interface conditions, including a matching device MAC. The dispatcher consults `PS_PCD_SECURITY_FLAG`. Live testing showed `I/0x18` reaches its handler, then returns `0x20` outside a configuration session. A session opened with the existing administrator credential, accepted a same-value write with status `0x00`, and closed with status `0x00`. A zero-length password proof returned `0x10`; no authentication bypass was demonstrated.
3. Separately, `0x1a0908` reads `IP_HOST_NAME` from the `IP_CURRENT` scope and uses it in a `startup_dhcp.sh` command string passed to a `/bin/sh -c` wrapper. The local configuration routine at `0x19ef70` validates hostname characters before writing them. The ENPC writer's own branch shows length checks rather than that character validation.

## Missing link

The ENPC writer stores `IP_HOST_NAME` under the `IP` scope. The DHCP launcher reads `IP_CURRENT`. The code that copies or applies a value between those scopes, and the conditions that trigger the DHCP launcher, must be verified. On this live printer, an authenticated write of a harmless shell expression to the hostname field returned status `0x00` but did **not** change the field: `PS_COMMON_DEVICE_NAME_INDIVIDUALLY_SET` was clear, so the handler ignored the supplied hostname. An analogous domain-field expression returned status `0x10` and did not change the field. In both tests the original network fields were re-sent and verified unchanged before the session closed. This ENPC route has not established shell-character storage or command execution.

## Safe next verification

Trace the independent Web Config setter and the device-name mode flag before further live writes. Then verify the `IP` to `IP_CURRENT` transition and command construction. A live execution proof should use a reversible, non-persistent marker with an observed response and preserve network reachability. Only after a reproducible security impact should this be promoted to a disclosure report.
