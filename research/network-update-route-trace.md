# ET-3850 network update route trace

The XB22Q5 `nwsoc` image contains a six-entry HTTP route table for firmware update paths. [`inspect_network_update_routes.py`](../scripts/inspect_network_update_routes.py) reproduces the table from a separately extracted `nwsoc` binary. The table has paired port 80 and port 443 entries:

| Method and path | Port 80 callback | Port 443 callback |
| --- | --- | --- |
| `GET /FIRMWAREUPDATE` | `0x15593c` | `0x155b98` |
| `GET /FIRMWAREUPDATE/ADMINCHECK` | `0x153b44` | `0x15398c` |
| `POST /DOWN/FIRMWAREUPDATE` | `0x1553b0` | `0x1555e8` |

The table establishes that this firmware was built with POST callbacks for the `/DOWN/FIRMWAREUPDATE` prefix. It does **not** show that `/DOWN/FIRMWAREUPDATE/ROM1` will accept an RCX in normal mode. The earlier live checks used HEAD on other routes and GET on these uppercase routes; no POST body was sent.

Decompilation shows that the port 443 GET and POST callbacks call `0x1534fc` when a global protection flag equals 1. That routine reads `PS_ADMIN_PASSWORD` and parses an HTTP `Authorization: Basic` header; failed authentication produces HTTP 401. When that flag equals 1, the port 80 GET and POST callbacks return HTTP 403 instead of asking for Basic credentials. This looks like a deliberate policy split, not an authentication bypass. The observed first unauthenticated port 80 GET of `/FIRMWAREUPDATE` returned 200; later GETs returned 500 while the printer remained usable. The flag's value during that live probe was not measured, and no sustained denial of service was shown.

Both POST callbacks eventually call `0x155180`, which enters the common HTTP parser at `0x154708`. A deeper XB22Q5 trace follows its parsed request to dispatcher `0x1543D0`. Dispatch type `0x0C` calls `0x115574`, then `0x0F5748`. That helper builds an internal `URI:` message from the request path (`0x0EE4C8`) and passes it to a configured transport channel (`0x42479C`, then `0x421F4C`). The channel function frames and writes the message through a connection handle. The response path reads from that channel (`0x424624`) and parses an HTTP-like response in `0x0F5014`. This is stronger evidence of an internal relay than of a direct Linux file write.

The update-preparation function at `0x16DE88` installs the transport callback at `0x156A3C` through `0x11634C` and a second callback at `0x1528E8` through `0x1162F0`. The former forwards HTTP headers and body chunks through the common channel routines; the latter handles the paired stream response. This explains why merely finding a POST route in the static table was insufficient: update preparation changes which callbacks and service state are active. It also narrows the remaining question to the channel peer and its signature check.

The trace does not yet identify the channel peer, its firmware payload handling, or where signature verification occurs. The signed RCX test shows that a payload edit invalidates its existing ECDSA signature. A route-table entry and relay path therefore do not establish a way to install modified firmware.

The route names match a [2016 researcher advisory about a WF-2540](https://lists.openwall.net/bugtraq/2016/09/26/2), which used `GET /FIRMWAREUPDATE` followed by `POST /DOWN/FIRMWAREUPDATE/ROM1`. That advisory tested a different printer and predates this signed XB20 package. Its unsigned-firmware conclusion must not be transferred to the ET-3850.

Next offline trace: identify the transport channel peer and firmware-specific body callback, then determine where the relayed bytes are authenticated. No new ET-3850 vulnerability or working network flash has been demonstrated.
