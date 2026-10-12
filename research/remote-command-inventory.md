# Controller remote command inventory

The XB22Q5 controller has a 15-entry two-letter command table at `0x45b7c2b8`.
The generic router at `0x459ae940` can receive requests through a private
SNMP OID. The [hash-checked inspector](../scripts/inspect_remote_command_table.py)
reproduces the table from decoded controller CROM segment 0.

Nine command names are present within that segment. Six name pointers refer to
memory outside the extracted segment, so their handlers can be named by address
but their two-letter keys have not been recovered from this image.

| Entry | Key | Handler | Static observation |
| --- | --- | --- | --- |
| 0 | unresolved | `0x459aee0c` | Formats an `EJL ID` reply after a one-byte request. |
| 1 | `st` | `0x459aef04` | Status reply. |
| 2 | `ti` | `0x459af6b4` | Validates an eight-byte date/time and sends it to an internal call. |
| 3 | unresolved | `0x459af1b8` | Conditionally forwards internal command `0x80`. |
| 4 | `rj` | `0x459af844` | Compares request bytes with stored data before forwarding internal command `0x81`. |
| 5 | unresolved | `0x459af94c` | Reads a one-byte stored value into a reply. |
| 6 | `vi` | `0x459afb5c` | Formats version and related status fields. |
| 7 | `pc` | `0x459b00a4` | Returns a one-byte keyed value through a controller helper. |
| 8 | `gm` | `0x459b0494` | Selects internal commands `0x82` and `0x83` for two one-byte inputs. |
| 9 | `||` | `0x459b0a4c` | Gated inner command table, including setup `p` and `q`. |
| 10 | `cx` | `0x459aef74` | Reads a stored flag into a reply. |
| 11 | unresolved | `0x459b0168` | Reads or formats records depending on its one-byte mode. |
| 12 | `rw` | `0x459b0564` | Has stored-flag, token, and date/time checks before some internal actions. |
| 13 | unresolved | `0x459b0864` | Calls another controller helper when a condition is met. |
| 14 | unresolved | `0x459af288` | Dispatches through a three-entry subtable after a five-byte key comparison. |

The public SNMP `GET` tunnel on the test printer returned `vi:00:XB22Q5` for
the read-only `vi` byte-`0` request. Earlier read-only `st` probes also returned
status. The `||` dispatcher returned command-specific `NA` for harmless setup
probes. These replies establish exposure of the outer command router, not a
successful maintenance action or file write. The controller's `0x80`–`0x85`
internal command family has additional conditions; its role in firmware
installation has not been shown.

Do not treat table entries as security findings solely because they are hidden.
A report needs a reachable operation, its authorization context, and a concrete
impact. See [remote setup dispatch](remote-setup-dispatch.md) and
[vulnerability notes](vulnerabilities.md).
