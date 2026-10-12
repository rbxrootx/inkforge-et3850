# `ip neigh` address copy: static memory safety lead

The ET-3850 XB22Q5 `nwsoc` binary contains a potential stack overflow in its peer-address lookup. This is an **offline code finding**, not a demonstrated exploit on the printer. Addresses below are virtual addresses in the extracted ARM program; the corresponding file offsets are `address - 0x10000`.

## Code path

`FUN_00587854` handles a wireless peer connection and, in the branch where the interface mode is not `2` and the peer state is `5` or `6`, derives a peer MAC address, executes `fping -A -g %s %s`, and calls `FUN_00580ee8(local_150, acStack_78)`. The first argument is `local_150[16]`; the second is the formatted peer MAC. The caller later runs `ping -c 1 %s` using `local_150` and converts it with `inet_addr()`.

`FUN_00580ee8` at `0x580ee8` opens `ip neigh` with `popen()`, reads lines with `fgets()`, and selects the first line containing the peer MAC via `strstr()`. It calls `strtok()` on that line, takes the first token as the address, then does:

```c
size_t n = strlen(first_token);
strncpy(address_out, first_token, n);
address_out[n] = '\0';
```

There is no size argument or length check for `address_out`. A 16-character token already writes its terminator one byte beyond the caller's 16-byte buffer; longer tokens copy beyond it. The program invokes `ip neigh` without a `-4` family filter. The [Linux `ip-neighbour` manual](https://man7.org/linux/man-pages/man8/ip-neighbour.8.html) documents IPv4 and IPv6 neighbor addresses. An IPv6 neighbor entry whose MAC matches the selected peer could therefore supply a first token longer than 15 characters. The firmware also includes a DHCPv6 client configuration for `eth0` and `wlan0`, but this does not prove IPv6 neighbors appear in the specific peer state.

## Limits and next proof

The precise wireless mode and peer state prerequisites must be reproduced, and the printer's own `ip neigh` implementation and output order must be checked. No crafted neighbor entry was created on the live printer, no overflow was triggered there, and no instruction-pointer control or firmware write has been shown. This lead does **not** supply a working custom-firmware installation route.

A safe validation path is to reproduce the parser in an isolated ARM harness with a synthetic `ip neigh` line, then use a non-destructive device test only if the connection prerequisites and recovery method are known. A security report should identify the exact reachable mode, affected firmware, observed effect, and the smallest reproducible input without publishing device credentials.
