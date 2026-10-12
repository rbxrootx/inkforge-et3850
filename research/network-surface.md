# Live network surface

Read-only observation of a local ET-3850 on firmware `05.15.XB22Q5`:

- mDNS advertises `_ipp._tcp`, `_printer._tcp`, and `_pdl-datastream._tcp` as `EPSON ET-3850 Series`.
- TCP listeners observed: 80, 443, 515, 631, and 9100. The web page redirects HTTP to HTTPS.
- Web Config exposes status and an administrator interface. Its normal Firmware Update page checks for Epson updates; it is not an arbitrary RCX upload form.
- The official Windows updater executable contains network endpoints such as `/firmwareupdate/checknew` and `/firmwareupdate/writenew`. Decompilation shows an HTTP POST flow and an ECDSA P-256 verification path; printer-side enforcement has not been independently exercised. See [the updater trace](updater-signature.md).
- The extracted ARM application also contains uppercase `/FIRMWAREUPDATE` and `/FIRMWAREUPDATE/ADMINCHECK` strings. A first unauthenticated GET of `/FIRMWAREUPDATE` over HTTP returned 200; repeat GETs over HTTP and HTTPS returned 500. The other uppercase paths returned 404. The device remained reachable and its Basic page still showed the original name. No firmware data was uploaded. The first 200 response was not captured, so its semantics remain unknown; this is not an installation method.
- The extracted `nwsoc` image includes `/opt/nwsoc/public_key/enup.pem` and an ENUP authentication path. Successful authentication creates `/tmp/enup_auth_success`, after which a watcher starts Telnet. Static inspection shows a random challenge and one-time-password comparison. No valid authentication or bypass has been found.
- Static analysis identifies an `EPSON` packet parser bound to UDP 3289. A read-only `N` request received a 14-byte `EPSONn` response from that port on the live printer. An authenticated configuration session accepted a same-value write and left the network fields unchanged. A zero-length password proof was rejected. The [ENPC/DHCP lead](enpc-dhcp-lead.md) records the remaining command-injection questions.
- The [administrator API and URL inventory](admin-api-inventory.md) records Web Config forms, WS-Config SOAP actions, updater paths, and outbound Epson cloud addresses found in the extracted binaries.

The live printer was not flashed. Authenticated, reversible configuration probes were performed; subsequent readback showed its original Device Name and network fields. Its short 30-packet ping baseline had 0% loss and 1-16 ms responses; that sample does not reproduce an intermittent Wi-Fi fault.

## Network update gate

The official Windows updater has a generic network POST transport and resolves `BCryptVerifySignature` dynamically. Its verification path checks a SHA-256 digest and an ECDSA P-256 signature. The ET-3850 RCX contains a matching-size `EPSONSIGN` block, but the exact model path and device-side checks remain unresolved. The official recovery package is documented as USB-only; no signed custom package or verified network flashing path has been established. Do not send a modified image to a device with no proven recovery path.

A HEAD-only probe against those two routes on the live printer returned HTTP 404 over both HTTP and HTTPS. That is only a normal-mode, method-specific observation; it does not prove the routes are absent in an update or recovery mode. No firmware bytes were sent.

An Epson [security overview](https://support.epson.net/security/en/index.html) describes device-side firmware signature verification and secure boot for some product families. Its applicability to this ET-3850 has not been established; neither host-side checks nor that overview alone prove what the live printer will accept.
