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
IPL0_SHA256 = "bf046b5bd5f5499c377bcbcb7b27aeb7d298cdf897600123f3f613bb8d2b7903"
LOAD_BASE = 0x4566FF74
PROVISIONAL_BASE = 0x45670000
SHIFT = PROVISIONAL_BASE - LOAD_BASE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    parser.add_argument("--ipl0-code", type=Path,
                        help="raw XB22Q5 first IPL code; reconstructs copied RAM callback table")
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

    def jump_target(address: int) -> int:
        instruction = word(address)
        assert (instruction >> 25) & 7 == 5, f"expected ARM branch at {address:#x}"
        displacement = instruction & 0xFFFFFF
        if displacement & 0x800000:
            displacement -= 0x1000000
        return address + 8 + displacement * 4

    def branch_target(address: int) -> int:
        assert word(address) >> 24 == 0xEB, f"expected ARM BL at {address:#x}"
        return jump_target(address)

    def has_bl(start: int, end: int, target: int) -> bool:
        return any(
            branch_target(address) == target
            for address in range(start, end, 4)
            if word(address) >> 24 == 0xEB
        )

    local_table = word(provisional(0x4590ED7C))
    get_request_record = local_table + 8
    get_request_name = word(get_request_record)
    get_request_callback = word(get_request_record + 4)
    assert string(get_request_name) == b"GetRequestID"
    assert get_request_callback == provisional(0x45912740)

    path = word(provisional(0x459133F8))
    assert string(path) == b"/DOWN/FIRMWAREUPDATE/"
    rom_reply = word(provisional(0x459133FC))
    assert rom_reply == provisional(0x45912640)

    group76_table = provisional(0x45809A18)
    assert word(provisional(0x45809A10)) == 0x379FF100
    prep_handler = word(group76_table + 6 * 4)
    assert prep_handler == provisional(0x45809AA0)
    prep_call = provisional(0x45809AA8)
    prep_function = branch_target(prep_call)
    assert prep_function == provisional(0x45808B2C)
    rom_handler = word(group76_table + 8 * 4)
    assert rom_handler == provisional(0x45809AB8)
    rom_selector = provisional(0x458089A4)
    assert data[rom_selector - LOAD_BASE : rom_selector - LOAD_BASE + 4] == bytes.fromhex("f8402de9")
    assert word(0x45808A18) == 0xE3010132  # ROM1: movw r0, #0x1132
    assert branch_target(0x45808A1C) == 0x458AA1D0  # store allocated request ID

    group5_table = provisional(0x4589E4B0)
    assert word(provisional(0x4589E4A8)) == 0x379FF101
    group5_handler = word(group5_table + 3 * 4)
    assert group5_handler == provisional(0x4589E504)

    callback_list_table = word(provisional(0x457E8A78))
    callback_list = word(callback_list_table + 0xB * 4)
    assert [word(callback_list + i * 4) for i in range(3)] == [0x11, 0x12, 0xFFFFFFFF]
    runtime_callback_table = word(provisional(0x457E8A70))
    assert runtime_callback_table == 0x43EAE878

    group77_table = provisional(0x45777814)
    group77_targets = [word(group77_table + i * 4) for i in range(6)]
    assert group77_targets == [
        provisional(0x45777874), provisional(0x4577782C),
        provisional(0x45777834), provisional(0x45777844),
        provisional(0x45777864), provisional(0x45777854),
    ]
    group77_source = branch_target(group77_targets[3])
    group77_receiver = branch_target(group77_targets[5])
    assert group77_source == provisional(0x45777638)
    assert group77_receiver == provisional(0x45777488)
    group77_sender = word(0x45ADA4D4)
    assert group77_sender == provisional(0x45776E44)
    assert has_bl(group77_source, 0x45777678, 0x45777534)
    assert has_bl(0x45777534, 0x4577759C, 0x4577704C)
    assert has_bl(group77_receiver, 0x45777530, provisional(0x45778404))
    stream_ingress = word(0x457E89F0)
    stream_read = word(0x457E89F4)
    assert (stream_ingress, stream_read) == (0x457E8130, 0x457E7FE0)
    rom1_source_read = word(0x457DBBC8)
    assert rom1_source_read == 0x457DB89C
    assert word(0x457DB8C8) == 0xE3010132  # movw r0, #0x1132
    assert word(0x457DB944) == 0xE3A00001  # mov r0, #1 (D4 channel)
    assert branch_target(0x457DB948) == 0x4589CCF4

    for allocator_call in (0x457289B0, 0x457289CC, 0x457289F8):
        assert branch_target(allocator_call) == 0x458AC5F8
    for size_instruction in (0x457289A4, 0x457289C0, 0x457289EC):
        assert word(size_instruction) == 0xE3A02401  # mov r2, #0x1000000

    # Completion after both ROM1 callbacks report done. The accepted package
    # remains in three allocated 16 MiB staging buffers at this point.
    assert branch_target(0x45776F84) == 0x4589E0D4  # ID 0x12 done -> event 5/5
    assert branch_target(0x457DB7B4) == 0x4589E0D4  # ID 0x11 done -> event 5/5
    group5_done = word(group5_table + 5 * 4)
    assert group5_done == 0x4589E490
    assert branch_target(0x4589E494) == 0x457E88D8
    assert branch_target(0x457E8934) == 0x457E881C  # all callbacks done?
    group76_done = word(group76_table + 5 * 4)
    assert group76_done == 0x45809A04
    assert branch_target(0x45809A0C) == 0x45809310
    assert jump_target(0x458093A0) == 0x45808BD4  # ROM1 completion
    assert word(0x45808BF8) == 0xE3000CA4  # movw r0, #0xca4 (success record)
    assert branch_target(0x45808BFC) == 0x458AA2D0
    assert branch_target(0x45808CFC) == 0x45728E18  # staging table
    assert branch_target(0x45808D00) == 0x4590B088  # external handoff
    assert branch_target(0x45808D08) == 0x458AAB00  # state event
    assert word(0x4590B0A8) == 0xE3A02030  # copy 0x30 staging metadata bytes
    assert branch_target(0x4590B0D0) == 0x456BEB84
    assert branch_target(0x4590B0E4) == 0x456BEB8C
    assert jump_target(0x456BEB84) == 0x4370D47C
    assert jump_target(0x456BEB8C) == 0x4370D588

    copied_callback_objects = None
    if args.ipl0_code:
        ipl = args.ipl0_code.read_bytes()
        assert hashlib.sha256(ipl).hexdigest() == IPL0_SHA256

        def ipl_word(offset: int) -> int:
            return struct.unpack_from("<I", ipl, offset)[0]

        source = ipl_word(0x56298)
        destination = ipl_word(0x5629C)
        length = ipl_word(0x562A0)
        assert (source, destination, length) == (0x57004, 0x43E90000, 0x4C844)
        table_source = source + runtime_callback_table - destination
        assert source <= table_source and table_source + 37 * 4 <= source + length
        copied_callback_objects = [ipl_word(table_source + i * 4) for i in range(37)]
        assert copied_callback_objects == [0x45ADA314 + i * 0x18 for i in range(37)]
        callback_11 = word(copied_callback_objects[0x11] + 0x10)
        callback_12 = word(copied_callback_objects[0x12] + 0x10)
        assert callback_11 == 0x457DBE3C
        assert callback_12 == group77_sender

    print(f"EpsonLocalReq:GetRequestID -> parser {get_request_callback:#x}")
    print(f"GET /FIRMWAREUPDATE -> event 0x76/6 -> prep handler {prep_handler:#x} "
          f"-> state function {prep_function:#x}")
    print(f"POST URI prefix {string(path).decode()} -> event 0x76/8")
    print(f"event 0x76/8 -> ROM handler {rom_handler:#x}; ROM selector {rom_selector:#x}")
    print(f"ROM request reply callback {rom_reply:#x}: static ChID 1, nonzero request ID for 200")
    print(f"ROM1 branch 0xb -> event 5/3 -> handler {group5_handler:#x}")
    print(f"branch 0xb callback IDs: 0x11, 0x12; runtime table {runtime_callback_table:#x}")
    print(f"group 0x77/3 sender {group77_sender:#x} -> source event {group77_source:#x}")
    print(f"group 0x77/5 -> package receiver {group77_receiver:#x}")
    print(f"ROM1 request ID record 0x1132 -> source read {rom1_source_read:#x} -> D4 channel 1; end marker queues 0x77/5")
    print(f"ROM1 reader result -> status record 0xca4 -> group 5/5 {group5_done:#x} -> group 0x76/5 {group76_done:#x}")
    print("status 0xca4 == 1 -> staged-buffer metadata -> external commands 0x2a and 0x2b at 0x4370d47c/0x4370d588")
    if copied_callback_objects is not None:
        print(f"IPL copy -> RAM callback table: source {source:#x}, destination {destination:#x}, length {length:#x}")
        print(f"ROM branch callback 0x11 -> {callback_11:#x}; 0x12 -> {callback_12:#x} (group 0x77/3 sender)")
    print("Static chain only: live body acceptance, external handoff validation, and flash commit are unproved")


if __name__ == "__main__":
    main()
