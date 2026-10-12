# Live network surface

Read-only observation of a local ET-3850 on firmware `05.15.XB22Q5`:

- mDNS advertises `_ipp._tcp`, `_printer._tcp`, and `_pdl-datastream._tcp` as `EPSON ET-3850 Series`.
- TCP listeners observed: 80, 443, 515, 631, and 9100. The web page redirects HTTP to HTTPS.
- Web Config exposes status and an administrator interface. Its normal Firmware Update page checks for Epson updates; it is not an arbitrary RCX upload form.
- The official Windows updater executable contains network endpoints such as `/firmwareupdate/checknew` and `/firmwareupdate/writenew`, plus `BCryptVerifySignature` and signature-verification error strings. This establishes host-side signature checking; printer-side enforcement has not been independently exercised.
- The extracted `nwsoc` image includes `/opt/nwsoc/public_key/enup.pem` and an ENUP authentication path. Successful authentication creates `/tmp/enup_auth_success`, after which a watcher starts Telnet. Static inspection shows a random challenge and one-time-password comparison. No valid authentication or bypass has been found.
- Static analysis identifies an `EPSON` packet parser bound to UDP 3289. A single read-only `N` request received a 14-byte `EPSONn` response from that port on the live printer, confirming reachability. Its hostname setter is described in the [ENPC/DHCP lead](enpc-dhcp-lead.md). The response does not establish whether configuration writes require authentication; packet security state is unknown.

The live printer was not flashed or reconfigured during this analysis. Its short 30-packet ping baseline had 0% loss and 1-16 ms responses; that sample does not reproduce an intermittent Wi-Fi fault.

## Network update gate

The official Windows updater includes `/firmwareupdate/checknew` and `/firmwareupdate/writenew` transport strings, and `BCryptVerifySignature` plus firmware-signature error strings. This shows a network transport exists in the generic updater and that the host checks signatures. The official ET-3850 recovery package is documented as USB-only; no signed custom package or verified network flashing path has been established. Whether the printer independently checks a modified image remains unresolved. Do not send a modified image to a device with no proven recovery path.

A HEAD-only probe against those two routes on the live printer returned HTTP 404 over both HTTP and HTTPS. That is only a normal-mode, method-specific observation; it does not prove the routes are absent in an update or recovery mode. No firmware bytes were sent.
