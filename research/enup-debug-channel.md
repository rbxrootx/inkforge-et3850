# ENUP debug authentication on XB22Q5

The extracted `nwsoc` program contains an ENUP maintenance channel. Its receive
loop creates an IPv4 raw socket with protocol number `0xf8` (248), rather than a
TCP or UDP listener. A boot script waits for `/tmp/enup_auth_success` and starts
`telnetd` if that file appears. This is a possible device-side command channel,
but a successful network authentication or Telnet session has **not** been
observed on the ET-3850.

## What this channel is for

The static command dispatch shows a service and debugging interface. Once
`/tmp/enup_auth_success` exists, command `4` removes the persistent
`enup_auth_ready_flag`, command `5` redirects standard output and error to a
`/dev/ttyp%d` device, command `6` creates `/tmp/gdbserver_start`, and command
`7` writes NFS configuration fields under `/opt/nwsoc_data/nfs_info/`:
`nfs_flag`, `client_ip`, `server_ip`, and `mac_addr`. A separate watcher sees
`/tmp/gdbserver_start` and attempts to launch `gdbserver` on port `2000`
against `nwsoc`. Its command line contains `--attatch`, so whether it actually
starts is unverified. The Telnet watcher starts `telnetd` once
`/tmp/enup_auth_success` appears.

The RSA step gates these capabilities: the device encrypts a fresh challenge
with the embedded public key and compares the returned 32-byte plaintext to
the challenge. The corresponding private key would be needed to produce a
valid answer by the intended protocol. The public key itself does not grant
access. This is an inference from the extracted code, not a vendor description
of ENUP's purpose. No command was exercised on the live printer.

## Static authentication trace

In the XB22Q5 `nwsoc` image (SHA-256
`70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0`),
`FUN_0022dc30` at `0x0022dc30` checks `/tmp/enup_auth_success` and
`/opt/nwsoc_data/enup_auth_ready_flag` before entering its protocol stages.
The second stage reads 32 bytes from `/dev/urandom`, overwrites the initial
bytes with decimal nanoseconds, encrypts the resulting 32-byte challenge with
`/opt/nwsoc/public_key/enup.pem`, and sends it. It accepts a response only
when its 32 decoded bytes match the challenge; the response bytes are XORed
with `0xaaaaaaaa` before the comparison. On that branch it executes
`touch /tmp/enup_auth_success`. The embedded PEM is a 2048-bit RSA public key
with exponent 65537. The corresponding private key is not in the extracted
image.

`FUN_0022da38` at `0x0022da38` receives into a `0x41b`-byte allocation and
uses the IPv4 total-length field at packet offset 2 when it is at most
`0x419`. It subtracts the first `recv()` count from that field without an
explicit count-versus-declared-length check. A synthetic receive result larger
than the declared IP length would underflow the remaining length, but a normal
IP stack is expected to deliver a packet according to its total-length field.
There is **no confirmed reachable overflow** from this observation. A real
report would require showing that the device's raw socket receives such a
packet and that a subsequent receive writes beyond the allocation.
The raw IPv4 socket normally receives a complete datagram as one packet, with
lengths constrained by the IP stack; that makes the underflow condition
uncertain in practice. The function also accepts a positive short return
without checking the minimum ENUP header length before its caller reads fixed
offsets.

The handler clears only four bytes of its `0x41b`-byte receive allocation
between stages. A short packet can leave stale bytes in the rest of that
buffer; this is an additional parser audit lead, not a demonstrated bypass.

## Reproduction and limit

Run `python scripts/inspect_enup_auth.py <extracted-nwsoc>` to check the
relevant constants and strings against the hash-locked image. This is offline
only. No ENUP packet was sent to the printer during this trace. The observed
Web Config administrator login does not supply this challenge response, and
neither flag file has a proven arbitrary network write route. This path is
therefore not an installation method for the custom Wi-Fi image yet.
