# ET-3850 network update route trace

The XB22Q5 `nwsoc` image contains a six-entry HTTP route table for firmware update paths. [`inspect_network_update_routes.py`](../scripts/inspect_network_update_routes.py) reproduces the table from a separately extracted `nwsoc` binary. The table has paired port 80 and port 443 entries:

| Method and path | Port 80 callback | Port 443 callback |
| --- | --- | --- |
| `GET /FIRMWAREUPDATE` | `0x15593c` | `0x155b98` |
| `GET /FIRMWAREUPDATE/ADMINCHECK` | `0x153b44` | `0x15398c` |
| `POST /DOWN/FIRMWAREUPDATE` | `0x1553b0` | `0x1555e8` |

The table establishes that this firmware was built with POST callbacks for the `/DOWN/FIRMWAREUPDATE` prefix. It does **not** show that `/DOWN/FIRMWAREUPDATE/ROM1` will accept an RCX in normal mode. The earlier live checks used HEAD on other routes and GET on these uppercase routes; no POST body was sent.

Decompilation shows that the port 443 GET and POST callbacks call `0x1534fc` when a global flag equals 1. That routine reads `PS_ADMIN_PASSWORD` and parses an HTTP `Authorization: Basic` header. The port 80 callbacks do not call this routine in their own code. A separate web-server layer, route state, or device configuration may still constrain port 80. The observed first unauthenticated port 80 GET of `/FIRMWAREUPDATE` returned 200; later GETs returned 500 while the printer remained usable. This is an authorization research lead, not a confirmed bypass or denial of service.

Both POST callbacks eventually call `0x155180`, which enters the common HTTP parser at `0x154708`; the complete upload sink and printer-side signature check remain untraced. The signed RCX test shows that a payload edit invalidates its existing ECDSA signature. A route-table entry therefore does not establish a way to install modified firmware.

The route names match a [2016 researcher advisory about a WF-2540](https://lists.openwall.net/bugtraq/2016/09/26/2), which used `GET /FIRMWAREUPDATE` followed by `POST /DOWN/FIRMWAREUPDATE/ROM1`. That advisory tested a different printer and predates this signed XB20 package. Its unsigned-firmware conclusion must not be transferred to the ET-3850.

Next offline trace: follow `0x154708` to the route-specific upload sink and determine whether it passes bytes to the main controller, writes Linux storage, or verifies a signature. No new ET-3850 vulnerability or working network flash has been demonstrated.
