#!/usr/bin/env python3
"""Probe an ET-3850 update URL with an invalid marker and sample uptime.

This is a diagnostic request to a user-controlled printer. It is not firmware.
The body lacks RCX and EPSONSIGN headers and must not be treated as an install
test. --prepare-only sends no POST. A preparation GET followed by a marker
POST caused a network/SNMP uptime reset in one observation.
"""

import argparse
import socket
import time

from pysnmp.hlapi import (
    CommunityData, ContextData, ObjectIdentity, ObjectType,
    SnmpEngine, UdpTransportTarget, getCmd,
)


PATH = "/DOWN/FIRMWAREUPDATE/ROM1"
MARKER = b"ET3850-INVALID-PROBE"
UPTIME_OID = "1.3.6.1.2.1.1.3.0"


def uptime(host: str) -> str:
    err, status, _, binds = getCmd(
        SnmpEngine(), CommunityData("public", mpModel=1),
        UdpTransportTarget((host, 161), timeout=2, retries=0),
        ContextData(), ObjectType(ObjectIdentity(UPTIME_OID)),
    )
    if err or status or not binds:
        return f"unavailable ({err or status})"
    return str(int(binds[0][1]))


def send_http(host: str, method: str, path: str, body: bytes) -> bytes:
    request = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Content-Type: application/octet-stream\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + body
    with socket.create_connection((host, 80), timeout=5) as sock:
        sock.settimeout(10)
        sock.sendall(request)
        chunks = []
        total = 0
        while total < 4096:
            try:
                part = sock.recv(min(1024, 4096 - total))
            except socket.timeout:
                print(f"{method} receive_timeout", flush=True)
                break
            if not part:
                break
            chunks.append(part)
            total += len(part)
    return b"".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="IP address of a printer you control")
    parser.add_argument("--prepare", action="store_true",
                        help="issue one GET /FIRMWAREUPDATE before the marker POST; "
                             "skip POST unless GET returns 200")
    parser.add_argument("--prepare-only", action="store_true",
                        help="issue the preparation GET and sample uptime; do not POST")
    args = parser.parse_args()
    host = args.host

    print(f"pre_uptime_centiseconds={uptime(host)}", flush=True)
    if args.prepare or args.prepare_only:
        prep = send_http(host, "GET", "/FIRMWAREUPDATE", b"")
        prep_status = prep.partition(b"\r\n")[0]
        print(f"prepare_status={prep_status.decode('ascii', 'replace')}", flush=True)
        print(f"post_prepare_uptime_centiseconds={uptime(host)}", flush=True)
        if args.prepare_only:
            previous = 0
            for delay in (5, 15, 30):
                time.sleep(delay - previous)
                print(f"prepare_only_uptime_after_{delay}s={uptime(host)}", flush=True)
                previous = delay
            return
        if b" 200 " not in prep_status:
            print("marker_post_skipped: preparation did not return 200", flush=True)
            return
        time.sleep(2)

    response = send_http(host, "POST", PATH, MARKER)
    head = response.partition(b"\r\n\r\n")[0]
    print(f"sent_marker_bytes={len(MARKER)} response_bytes={len(response)}", flush=True)
    print(head.decode("iso-8859-1", "replace"), flush=True)
    for delay in (0, 5, 15):
        if delay:
            time.sleep(delay)
        print(f"post_uptime_centiseconds_after_{delay}s={uptime(host)}", flush=True)


if __name__ == "__main__":
    main()
