#!/usr/bin/env python3
"""Check the XB22Q5 controller's first-stage ROM update dispatch offline.

Supply decoded CROM segment 0 from extract_controller_crom.py. This script
uses fixed source-hash and address assertions; it does not contact a printer.
"""

import argparse
import hashlib
from pathlib import Path
import struct


SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
LOAD_BASE = 0x4566FF74
PROVISIONAL_BASE = 0x45670000
SHIFT = PROVISIONAL_BASE - LOAD_BASE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    args = parser.parse_args()
    data = args.controller_segment.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        parser.error("input is not the expected XB22Q5 controller segment 0")

    def word(runtime: int) -> int:
        at = runtime - LOAD_BASE
        if not 0 <= at <= len(data) - 4:
            raise ValueError(f"address outside CROM: {runtime:#x}")
        return struct.unpack_from("<I", data, at)[0]

    def string(runtime: int) -> bytes:
        at = runtime - LOAD_BASE
        if not 0 <= at < len(data):
            raise ValueError(f"string outside CROM: {runtime:#x}")
        return data[at : at + 96].split(b"\0", 1)[0]

    def provisional(address: int) -> int:
        return address - SHIFT

    local_table = word(provisional(0x4590ED7C))
    get_request_record = local_table + 8
    get_request_name = word(get_request_record)
    get_request_callback = word(get_request_record + 4)
    assert string(get_request_name) == b"GetRequestID"
    assert get_request_callback == provisional(0x45912740)

    path = word(provisional(0x459133F8))
    assert string(path) == b"/DOWN/FIRMWAREUPDATE/"

    group76_table = provisional(0x45809A18)
    assert word(provisional(0x45809A10)) == 0x379FF100
    rom_handler = word(group76_table + 8 * 4)
    assert rom_handler == provisional(0x45809AB8)
    rom_selector = provisional(0x458089A4)
    assert data[rom_selector - LOAD_BASE : rom_selector - LOAD_BASE + 4] == bytes.fromhex("f8402de9")

    group5_table = provisional(0x4589E4B0)
    assert word(provisional(0x4589E4A8)) == 0x379FF101
    group5_handler = word(group5_table + 3 * 4)
    assert group5_handler == provisional(0x4589E504)

    callback_list_table = word(provisional(0x457E8A78))
    callback_list = word(callback_list_table + 0xB * 4)
    assert [word(callback_list + i * 4) for i in range(3)] == [0x11, 0x12, 0xFFFFFFFF]
    runtime_callback_table = word(provisional(0x457E8A70))
    assert runtime_callback_table == 0x43EAE878

    print(f"EpsonLocalReq:GetRequestID -> parser {get_request_callback:#x}")
    print(f"POST URI prefix {string(path).decode()} -> event 0x76/8")
    print(f"event 0x76/8 -> ROM handler {rom_handler:#x}; ROM selector {rom_selector:#x}")
    print(f"ROM1 branch 0xb -> event 5/3 -> handler {group5_handler:#x}")
    print(f"branch 0xb callback IDs: 0x11, 0x12; runtime table {runtime_callback_table:#x}")
    print("Static chain only: live acceptance, streamed body callback, and signature gate are unproved")


if __name__ == "__main__":
    main()
