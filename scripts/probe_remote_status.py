#!/usr/bin/env python3
"""Read-only Epson Remote Mode status probe over SNMPv2c.

Only reports the response type and length. It does not print or save the
status payload, which may contain device identifiers.
"""

import argparse
from pysnmp.hlapi import (
    CommunityData, ContextData, ObjectIdentity, ObjectType,
    SnmpEngine, UdpTransportTarget, getCmd,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Printer IP address")
    args = parser.parse_args()

    # "st", little-endian payload length 1, payload byte 1.
    oid = "1.3.6.1.4.1.1248.1.2.2.44.1.1.2.1.115.116.1.0.1"
    error, status, index, bindings = getCmd(
        SnmpEngine(), CommunityData("public", mpModel=1),
        UdpTransportTarget((args.host, 161), timeout=2, retries=0),
        ContextData(), ObjectType(ObjectIdentity(oid)),
    )
    if error:
        print(f"transport error: {error}")
        return 1
    if status:
        print(f"SNMP error: {status.prettyPrint()} at index {index}")
        return 1
    for returned_oid, value in bindings:
        print(
            f"oid_match={str(returned_oid) == oid} "
            f"type={type(value).__name__} "
            f"length={len(value.asOctets()) if hasattr(value, 'asOctets') else 'n/a'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
