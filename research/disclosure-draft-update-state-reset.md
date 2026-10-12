# Draft for vendor triage: update-state request sequence resets network uptime

**Status:** One combined live observation on an ET-3850 reporting `05.15.XB22Q5`. The network service recovered. A reproducible denial of service, physical reboot, and firmware acceptance are **not** established. This draft has not been submitted.

## Bounded observation

The device was reachable over Wi-Fi at its local address and reported `sysUpTime.0 = 2,688,100` centiseconds. An unauthenticated `GET /FIRMWAREUPDATE` on HTTP port 80 returned `200 OK`. An immediate SNMP check returned the same uptime. Two seconds later, an unauthenticated `POST /DOWN/FIRMWAREUPDATE/ROM1` carried the 20-byte ASCII body `ET3850-INVALID-PROBE`, with `Content-Length: 20` and `Content-Type: application/octet-stream`. The POST returned `500 Internal Server Error` with an empty body. SNMP timed out immediately and five seconds after the POST; at fifteen seconds it returned uptime `1,500` centiseconds. A later IPPS capability query showed idle printer state `3`.

The body is not an RCX or `EPSONSIGN` package. No image was flashed and no print was submitted.

## Controls and uncertainty

A previous standalone POST with the same invalid marker returned 500 while SNMP uptime increased throughout a 15-second window. A later single GET without POST returned 200 and uptime rose from `5,200` to `8,300` centiseconds over 30 seconds. A previous zero-byte POST was followed by a short outage and a low post-recovery uptime, but lacked a pre-request uptime value. These observations suggest that update preparation changes how the subsequent invalid POST is handled. They do not isolate the exact failing component, and the printer already has intermittent Wi-Fi problems. The combined sequence has not been repeated.

The [offline controller trace](controller-crom-trace.md) shows that `/FIRMWAREUPDATE` can queue a preparation event that advances update state toward `5`; a subsequent ROM1 POST is only accepted by its selector when state is `5`. The live state was not measured. The HTTP 500 response does not prove that the malformed marker reached the package parser.

## Triage request

Confirm whether this sequence restarts the network processor or SNMP agent, identify the failing component and whether preparation must complete first, and test whether an unauthorized LAN client can repeatedly interrupt service. The [bounded probe script](../scripts/probe_invalid_update_marker.py) supports `--prepare` and `--prepare-only`; it sends no firmware image. Avoid treating this draft as a confirmed security report until the sequence is reproduced and scoped.
