#!/usr/bin/env python3
"""Replay a harmless update-path marker only inside the isolated QEMU netns.

The target is fixed at the documentation address 192.0.2.2. This script
refuses to run when any other IPv4 interface or a default route is present.
It does not contact or install anything on a physical printer.
"""

import socket
import subprocess


HOST = "192.0.2.2"
MARKER = b"ET3850-OFFLINE-TEST"


def require_isolated_namespace() -> None:
    addresses = subprocess.check_output(
        ["ip", "-4", "-o", "addr", "show"], text=True
    ).splitlines()
    non_loopback = [line for line in addresses if " inet 127." not in line]
    if len(non_loopback) != 1 or " eth0 " not in non_loopback[0] or " inet 192.0.2.2/24 " not in non_loopback[0]:
        raise SystemExit("expected only isolated dummy eth0 at 192.0.2.2/24")
    if subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True).strip():
        raise SystemExit("refusing network namespace with a default route")


def request(method: str, path: str, body: bytes = b"") -> None:
    message = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + body
    with socket.create_connection((HOST, 80), timeout=3) as conn:
        conn.settimeout(3)
        conn.sendall(message)
        response = bytearray()
        while len(response) < 1024:
            try:
                chunk = conn.recv(1024 - len(response))
            except socket.timeout:
                break
            if not chunk:
                break
            response.extend(chunk)
    first_line = bytes(response).split(b"\r\n", 1)[0]
    print(method, path, "body_bytes", len(body), "response", first_line.decode("ascii", "replace"))


def main() -> None:
    require_isolated_namespace()
    request("GET", "/FIRMWAREUPDATE")
    request("POST", "/DOWN/")
    request("POST", "/DOWN/FIRMWAREUPDATE/ROM1", MARKER)


if __name__ == "__main__":
    main()
