#!/usr/bin/env python3
"""Probe the live ET-3850's remote `||` dispatcher without changing bytes.

The default requests have invalid command check bytes after the fixed `J6`
access bytes, so the handler rejects them before subcommand dispatch. With
--zero-copy, a matching `p` envelope carries
a type-2 operation with length zero. The decoded controller copy routine then
receives a zero-byte length; it cannot alter the setup buffer.
With --zero-read, the analogous `q` envelope requests zero bytes.
"""

import argparse

from pysnmp.hlapi import (
    CommunityData, ContextData, ObjectIdentity, ObjectType,
    SnmpEngine, UdpTransportTarget, getCmd,
)


BASE_OID = "1.3.6.1.4.1.1248.1.2.2.44.1.1.2.1"
INVALID_J6 = bytes((0x4A, 0x36, 0, 0, 0))
ZERO_COPY = bytes((0x4A, 0x36, 0x70, 0x8F, 0x38, 2, 0, 0, 0, 0, 0, 0))
ZERO_READ = bytes((0x4A, 0x36, 0x71, 0x8E, 0xB8, 2, 0, 0, 0, 0, 0, 0))


def query(host: str, label: str, command: bytes, body: bytes) -> None:
    request = command + len(body).to_bytes(2, "little") + body
    oid = BASE_OID + "." + ".".join(str(part) for part in request)
    error, status, index, bindings = getCmd(
        SnmpEngine(), CommunityData("public", mpModel=1),
        UdpTransportTarget((host, 161), timeout=2, retries=0),
        ContextData(), ObjectType(ObjectIdentity(oid)),
    )
    if error:
        print(f"{label}: transport={error}")
        return
    if status:
        print(f"{label}: status={status.prettyPrint()} index={index}")
        return
    for returned_oid, value in bindings:
        data = value.asOctets() if hasattr(value, "asOctets") else b""
        print(
            f"{label}: oid_match={str(returned_oid) == oid} "
            f"type={type(value).__name__} length={len(data)} "
            f"reply={data[:16].hex()}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="printer IPv4 address")
    parser.add_argument("--zero-copy", action="store_true",
                        help="also test a valid envelope with zero-byte copy")
    parser.add_argument("--zero-read", action="store_true",
                        help="also test a valid envelope with zero-byte read")
    args = parser.parse_args()
    query(args.host, "unknown", b"zz", INVALID_J6)
    query(args.host, "bad-checksum", b"||", INVALID_J6)
    if args.zero_copy:
        query(args.host, "zero-copy", b"||", ZERO_COPY)
    if args.zero_read:
        query(args.host, "zero-read", b"||", ZERO_READ)


if __name__ == "__main__":
    main()
