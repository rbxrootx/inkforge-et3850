#!/usr/bin/env python3
"""Check the XB22Q5 ENUP debug-auth constants in an extracted nwsoc image.

This reads a local firmware specimen only. It never contacts a printer.
"""

import argparse
import hashlib
import struct
from pathlib import Path


SHA256 = "70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0"
IMAGE_BASE = 0x10000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nwsoc", type=Path)
    args = parser.parse_args()
    blob = args.nwsoc.read_bytes()
    if hashlib.sha256(blob).hexdigest() != SHA256:
        parser.error("input is not the expected XB22Q5 nwsoc build")

    def word(address: int) -> int:
        return struct.unpack_from("<I", blob, address - IMAGE_BASE)[0]

    def cstring(address: int) -> str:
        offset = address - IMAGE_BASE
        if not 0 <= offset < len(blob):
            raise ValueError(f"string pointer {address:#x} outside image")
        end = blob.index(b"\0", offset)
        return blob[offset:end].decode("ascii")

    expected = {
        0x22EBEC: "/tmp/enup_auth_success",
        0x22EC04: "/opt/nwsoc_data/enup_auth_ready_flag",
        0x22EC24: "20031",
        0x22EC48: "touch /opt/nwsoc_data/enup_auth_ready_flag",
        0x22EC5C: "/dev/urandom",
        0x22EC68: "/opt/nwsoc/public_key/enup.pem",
        0x22EC70: "touch /tmp/enup_auth_success",
        0x22EDD0: "/dev/ttyp%d",
        0x22F130: "/opt/nwsoc_data/nfs_info",
        0x22F14C: "/opt/nwsoc_data/nfs_info/nfs_flag",
        0x22F15C: "/opt/nwsoc_data/nfs_info/client_ip",
        0x22F164: "/opt/nwsoc_data/nfs_info/server_ip",
        0x22F174: "/opt/nwsoc_data/nfs_info/mac_addr",
        0x22F1D8: "touch /tmp/gdbserver_start",
    }
    for ptr_at, text in expected.items():
        actual = cstring(word(ptr_at))
        if actual != text:
            raise ValueError(f"unexpected string at {ptr_at:#x}: {actual!r}")
        print(f"{ptr_at:#010x} -> {actual}")

    allocation = word(0x22EBF4)
    first_recv = word(0x22DC08)
    length_limit = word(0x22DC14)
    protocol = 0xF8  # Immediate argument in socket(AF_INET, SOCK_RAW, protocol).
    assert allocation == first_recv == 0x41B
    assert length_limit == 0x419
    print(f"raw IPv4 protocol={protocol}; allocation={allocation}; initial recv={first_recv}; length limit={length_limit}")
    print("auth reply: decompiled nonce comparison requires 32 matching bytes after XOR 0xaaaaaaaa")
    print("Caution: constants and static control flow do not establish live reachability or a bypass.")


if __name__ == "__main__":
    main()
