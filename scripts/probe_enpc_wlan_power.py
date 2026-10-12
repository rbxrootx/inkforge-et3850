#!/usr/bin/env python3
"""Read an ET-3850 ENPC WLAN power-mode byte without changing settings."""

import argparse
import socket


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address", help="Printer IPv4 address")
    args = parser.parse_args()
    target = (args.address, 3289)
    request = bytearray(b"EPSON" + b"I" + b"\0" * 8)
    request[8:10] = (0x96).to_bytes(2, "big")
    request[12:14] = (1).to_bytes(2, "big")
    request += b"\0"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(4)
        sock.sendto(request, target)
        response, peer = sock.recvfrom(512)
    if (peer != target or len(response) != 39 or
            response[:6] != b"EPSONi" or
            response[8:10] != b"\x00\x96" or
            response[12:14] != b"\x00\x19"):
        raise RuntimeError("unexpected response; no values printed")
    print("ENPC status:", response[10:12].hex())
    print("WLAN_POWER_MANAGEMENT_MODE byte:", response[0x14])


if __name__ == "__main__":
    main()
