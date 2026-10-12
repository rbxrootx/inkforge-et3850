"""Check the first IPL image's key copy descriptor against an XB20 RCX.

This is a static consistency check, not a printer trust or signature bypass test.
"""

import argparse
import hashlib
from pathlib import Path
import struct


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipl0", type=Path, help="raw first IPL code image")
    parser.add_argument("rcx", type=Path, help="corresponding RCX")
    args = parser.parse_args()
    boot = args.ipl0.read_bytes()
    rcx = args.rcx.read_bytes()
    if len(boot) < 0x13F040 or len(rcx) < 0xB162:
        raise ValueError("input is too short for the expected IPL0/RCX layout")
    source, destination, size = struct.unpack_from("<III", boot, 0x2EF4)
    parser_key_source, parser_key_dest = struct.unpack_from("<II", boot, 0xA298)
    copy_key = boot[source : source + 64]
    second_key = boot[0x13F000 : 0x13F040]
    rcx_key = rcx[0xB122 : 0xB162]
    print(f"Boot copy descriptor: 0x{source:x} -> 0x{destination:x}, 0x{size:x} bytes")
    print(f"EPSONSIGN parser key copy: 0x{parser_key_source:x} -> 0x{parser_key_dest:x}")
    print("Key SHA-256:", hashlib.sha256(copy_key).hexdigest())
    if (source, destination, size) != (0x7010, 0x46308000, 0x1000):
        raise ValueError("unexpected boot copy descriptor")
    if parser_key_source != destination:
        raise ValueError("parser does not read from boot copy destination")
    if copy_key != second_key or copy_key != rcx_key:
        raise ValueError("IPL key copies and RCX key differ")
    print("Both IPL key copies match the RCX embedded key.")


if __name__ == "__main__":
    main()
