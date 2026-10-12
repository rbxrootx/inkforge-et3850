"""List ET-3850 XB22Q5 firmware-update HTTP route table entries offline."""

import argparse
import hashlib
import struct
from pathlib import Path


EXPECTED_SHA256 = "70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0"
IMAGE_BASE = 0x10000
PATHS = (
    b"/FIRMWAREUPDATE",
    b"/FIRMWAREUPDATE/ADMINCHECK",
    b"/DOWN/FIRMWAREUPDATE",
)


def entries(blob: bytes):
    if hashlib.sha256(blob).hexdigest() != EXPECTED_SHA256:
        raise ValueError("unexpected nwsoc build")
    results = []
    for path in PATHS:
        string_offset = blob.find(path + b"\0")
        if string_offset < 0:
            raise ValueError(f"missing path: {path!r}")
        pointer = struct.pack("<I", string_offset + IMAGE_BASE)
        start = 0
        while (hit := blob.find(pointer, start)) >= 0:
            start = hit + 1
            if hit < 0x14 or hit + 0x18 > len(blob):
                continue
            method = blob[hit - 0x14 : hit - 0x10].rstrip(b"\0")
            if method not in (b"GET", b"POST"):
                continue
            callback = struct.unpack_from("<I", blob, hit + 0x0c)[0]
            port = struct.unpack_from("<I", blob, hit + 0x14)[0]
            if port not in (80, 443):
                raise ValueError(f"unexpected port at 0x{hit:x}: {port}")
            results.append((hit + IMAGE_BASE, method.decode(), path.decode(), port, callback))
    return sorted(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nwsoc", type=Path)
    args = parser.parse_args()
    for address, method, path, port, callback in entries(args.nwsoc.read_bytes()):
        print(f"0x{address:08x} {method:4} {path:31} port={port} callback=0x{callback:08x}")


if __name__ == "__main__":
    main()
