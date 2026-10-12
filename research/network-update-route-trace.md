# ET-3850 network update route trace

The XB22Q5 `nwsoc` image contains a six-entry HTTP route table for firmware update paths. [`inspect_network_update_routes.py`](../scripts/inspect_network_update_routes.py) reproduces the table from a separately extracted `nwsoc` binary. The table has paired port 80 and port 443 entries:

| Method and path | Port 80 callback | Port 443 callback |
| --- | --- | --- |
| `GET /FIRMWAREUPDATE` | `0x15593c` | `0x155b98` |
| `GET /FIRMWAREUPDATE/ADMINCHECK` | `0x153b44` | `0x15398c` |
| `POST /DOWN/FIRMWAREUPDATE` | `0x1553b0` | `0x1555e8` |

The table establishes that this firmware was built with POST callbacks for the `/DOWN/FIRMWAREUPDATE` prefix. It does **not** show that `/DOWN/FIRMWAREUPDATE/ROM1` will accept an RCX in normal mode. The earlier live checks used HEAD on other routes and GET on these uppercase routes; no POST body was sent.

Decompilation shows that the port 443 GET and POST callbacks call `0x1534fc` when a global protection flag equals 1. That routine reads `PS_ADMIN_PASSWORD` and parses an HTTP `Authorization: Basic` header; failed authentication produces HTTP 401. When that flag equals 1, the port 80 GET and POST callbacks return HTTP 403 instead of asking for Basic credentials. This looks like a deliberate policy split, not an authentication bypass. The observed first unauthenticated port 80 GET of `/FIRMWAREUPDATE` returned 200; later GETs returned 500 while the printer remained usable. The flag's value during that live probe was not measured, and no sustained denial of service was shown.

Both POST callbacks call `0x170440` before choosing `0x155180` or `0x17111c`. The former enters the common HTTP parser at `0x154708`. The parsed request reaches dispatcher `0x1543D0`. Its cases `5`, `6`, and `7` call `0x0F8EBC`; cases `1`, `2`, and `0x0C` call `0x115574` and then `0x0F5748`. The latter helper builds an internal `URI:` message from the request path (`0x0EE4C8`) and passes it to a configured transport channel (`0x42479C`, then `0x421F4C`). The response path reads from that channel (`0x424624`) and parses an HTTP-like response in `0x0F5014`. This is stronger evidence of an internal relay than of a direct Linux file write.

The `0x170440` branch is now identified as the `SSL_TLS_AUTO_REDIRECT_HTTPS` check. It reads that setting and a connection class; when redirect is selected, `0x17111c` builds a `307 Temporary Redirect` with an `https://` `Location`. It is **not** a second firmware upload parser. The earlier description of it as an unresolved alternate route selector was too broad.

The relay's send side can be followed one layer farther: `0x0F5748` passes the framed message to `0x42479C`, which calls `0x421F4C`. That routine writes the D4/EPIC channel through `0x4740D8`; the latter issues ioctl `0xC018FE02`. The update request therefore crosses the Linux-to-controller IPC boundary. The controller handler and firmware authentication decision remain unidentified; crossing this channel is not evidence that a modified image would be accepted.

The `0x0F8EBC` branch handles a two-stage internal exchange. It first reads an internal response with `0x0F1D4C`. When that status is `200`, its request-type cases `1` and `3` send body buffers through `0x0F867C` and then read a final response with `0x0F5014`. Cases `0` and `2` read the response without calling the body sender. The common HTTP parser initializes that request-type field to `0` and changes it to `1` for selected callback IDs `10`, `17`, and `19`; the firmware POST callback passes ID `7`. This static path suggests that the ordinary ID `7` callback does not forward POST body bytes through that function. Other callbacks, update-preparation state, and runtime changes still need tracing.

A broader [HTTP route-table scan](../scripts/inventory_http_route_table.py) also finds paired `POST /DOWN/` records, distinct from `POST /DOWN/FIRMWAREUPDATE`. Their callback at `0x1571f8` calls the common parser with ID `10`. When that parser's request-type branch is `1`, ID `10` sets its body-processing flag and calls `0x160e68`. This makes the generic route a plausible body carrier. The route matcher’s precedence for overlapping `/DOWN/` and `/DOWN/FIRMWAREUPDATE` prefixes, the controller’s interpretation of any body, and acceptance of a modified RCX are still unproved. No generic `/DOWN/` POST was sent to the printer.

The relay serializer at `0x0E7C00` confirms its request text uses `URI:%s`, an escape separator, and `Method:%s`. Method constants include `GET`, `POST`, `PUT`, and `DELETE`. This verifies that these functions package a request for the internal peer; it does not identify the peer's firmware validation logic.

The update-preparation function at `0x16DE88` installs the transport callback at `0x156A3C` through `0x11634C` and a second callback at `0x1528E8` through `0x1162F0`. The former forwards HTTP headers and body chunks through the common channel routines; the latter handles the paired stream response. This explains why merely finding a POST route in the static table was insufficient: update preparation changes which callbacks and service state are active. It also narrows the remaining question to the controller handler and its signature check.

The trace identifies the D4 controller-facing IPC boundary, but not the controller handler for the firmware POST, its payload handling, or where signature verification occurs. The signed RCX test shows that a payload edit invalidates its existing ECDSA signature. A route-table entry and relay path therefore do not establish a way to install modified firmware.

## One live empty-request observation

On 2026-10-12 UTC, a single unauthenticated HTTP/1.1 `POST /DOWN/FIRMWAREUPDATE/ROM1` with `Content-Length: 0` returned `500 Internal Server Error` with an empty body. A read-only SNMP status request succeeded just before it, timed out on the first two attempts after it, then succeeded again. One ping during the interruption failed and the next succeeded. After recovery, SNMP `sysUpTime.0` read `3600` centiseconds (36 seconds) at approximately 07:58:20 UTC; this is consistent with the network processor or SNMP agent restarting around the POST, but there is no pre-request uptime measurement and the printer already has an intermittent Wi-Fi fault. There was no firmware payload, no custom image installation, and no cake print. This is a **reproducibility lead**, not yet a confirmed denial-of-service vulnerability. Repeating a state-changing POST for confirmation would risk another interruption.

The separately decoded [controller CROM image](controller-crom-trace.md) contains an internal request route that enqueues event `0x0b/0x42`. Its static event table sends `0x42` back to the wait loop in this image. This is a negative result for that specific internal request path, not proof that the Linux firmware-update POST has no other peer or that the live controller has identical runtime contents.

A separate `Method:`/`URI:` parser in that image has a POST branch that queues group `0x76`, subcommand `8`. The decoded receive loop's [jump table](../scripts/inspect_update_event_dispatch.py) sends subcommand `8` into table data rather than the nearby `ROM1`/`ROM2` handler. The parser lacks an identified caller, and a running controller could have a different RAM table, so this cannot be used as evidence that the live POST reaches a flash writer.

The route names match a [2016 researcher advisory about a WF-2540](https://lists.openwall.net/bugtraq/2016/09/26/2), which used `GET /FIRMWAREUPDATE` followed by `POST /DOWN/FIRMWAREUPDATE/ROM1`. That advisory tested a different printer and predates this signed XB20 package. Its unsigned-firmware conclusion must not be transferred to the ET-3850.

Next offline trace: identify the controller's firmware-specific request handler and body callback, then determine where the relayed bytes are authenticated. No new ET-3850 vulnerability or working network flash has been demonstrated.
