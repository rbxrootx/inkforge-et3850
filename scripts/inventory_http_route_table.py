#!/usr/bin/env python3
"""List hash-matched XB22Q5 nwsoc HTTP route-table records offline.

Matches the record layout used by inspect_network_update_routes.py. A listed
route may still require authentication or a runtime state; no network traffic
is generated.
"""

import argparse
import hashlib
import struct
from pathlib import Path


SHA256 = "70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0"
BASE = 0x10000
METHODS = (b"GET\0", b"POST", b"HEAD", b"PUT\0", b"DELE")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nwsoc", type=Path)
    args = parser.parse_args()
    blob = args.nwsoc.read_bytes()
    if hashlib.sha256(blob).hexdigest() != SHA256:
        parser.error("input is not the expected XB22Q5 nwsoc build")

    rows = []
    for offset in range(0, len(blob) - 0x2C, 4):
        method = blob[offset : offset + 4]
        if method not in METHODS:
            continue
        pointer = struct.unpack_from("<I", blob, offset + 0x14)[0]
        port = struct.unpack_from("<I", blob, offset + 0x28)[0]
        callback = struct.unpack_from("<I", blob, offset + 0x20)[0]
        path_offset = pointer - BASE
        if port not in (80, 443) or not (0 <= path_offset < len(blob)):
            continue
        if blob[path_offset : path_offset + 1] != b"/":
            continue
        end = blob.find(b"\0", path_offset, path_offset + 256)
        if end < 0:
            continue
        try:
            path = blob[path_offset:end].decode("ascii")
        except UnicodeDecodeError:
            continue
        if not path.isprintable():
            continue
        name = "DELETE" if method == b"DELE" else method.rstrip(b"\0").decode()
        rows.append((name, path, port, callback, offset + BASE))

    for method, path, port, callback, address in sorted(set(rows)):
        print(f"{method:4} {path:65} port={port:3} callback={callback:#010x} record={address:#010x}")
    print(f"Total distinct records: {len(set(rows))}")


if __name__ == "__main__":
    main()
