#!/usr/bin/env python3
"""Reproduce an XB22Q5 controller header-table write in isolated ARM emulation.

Usage: python scripts/emulate_controller_header_index.py CONTROLLER_SEGMENT RCX
Inputs must be separately extracted/obtained; no printer is contacted.
Requires the Python unicorn package.
"""

import argparse
import hashlib
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP


SEGMENT_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
RCX_SHA256 = "103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675"
BASE = 0x45670000
ENTRY = 0x457779e0
TYPE_GATE = 0x457783b0
TABLE = 0x45c65a88
META = 0x45d65d6c
KEY_BUFFER = 0x45d660e4
SIGNATURE_BUFFER = 0x45d66124
TABLE_RECORDS = 0x25
TABLE_RECORD_SIZE = 0x14
META_RECORD_SIZE = 0x18
STACK = 0x10000000
HEADER = 0x12000000
RESULT = 0x13000000
STOP = 0x14000000


def run_case(image: bytes, original_header: bytes, index: int) -> tuple[int, int, int | None, list[tuple[int, int]]]:
    header = bytearray(original_header)
    struct.pack_into("<H", header, 0x38, index)
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(BASE, (len(image) + 0xfff) & ~0xfff)
    cpu.mem_write(BASE, image)
    cpu.mem_map(0x45c00000, 0x200000)
    cpu.mem_map(STACK, 0x10000)
    cpu.mem_map(HEADER, 0x1000)
    cpu.mem_write(HEADER, bytes(header))
    cpu.mem_map(RESULT, 0x1000)
    cpu.mem_map(STOP, 0x1000)
    cpu.mem_write(TABLE, (b"\xff" + b"\0" * 19) * TABLE_RECORDS)
    cpu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
    cpu.reg_write(UC_ARM_REG_R0, RESULT)
    cpu.reg_write(UC_ARM_REG_R1, HEADER)
    cpu.reg_write(UC_ARM_REG_LR, STOP)
    writes: list[tuple[int, int]] = []

    def on_code(uc: Uc, addr: int, size: int, user: object) -> None:
        if addr == STOP:
            uc.emu_stop()

    def on_write(uc: Uc, access: int, addr: int, size: int, value: int, user: object) -> None:
        if TABLE <= addr < TABLE + 0x3000 or META <= addr < META + 0x3000:
            writes.append((addr, size))

    cpu.hook_add(UC_HOOK_CODE, on_code)
    cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)
    cpu.emu_start(ENTRY, STOP, count=100000)
    if cpu.reg_read(UC_ARM_REG_PC) != STOP:
        raise RuntimeError(f"parser did not return: pc={cpu.reg_read(UC_ARM_REG_PC):#x}")
    parse_result = cpu.reg_read(UC_ARM_REG_R0)
    parsed_index = cpu.mem_read(RESULT, 1)[0]
    gate_result = None
    if parse_result == 1:
        # Mirror the package reader: it reloads the indexed table byte and
        # checks it with FUN_457783b0 before consuming the record's body.
        table_id = cpu.mem_read(TABLE + parsed_index * TABLE_RECORD_SIZE, 1)[0]
        cpu.reg_write(UC_ARM_REG_R0, table_id)
        cpu.reg_write(UC_ARM_REG_R1, RESULT + 4)
        cpu.reg_write(UC_ARM_REG_LR, STOP)
        cpu.emu_start(TYPE_GATE, STOP, count=10000)
        if cpu.reg_read(UC_ARM_REG_PC) != STOP:
            raise RuntimeError("type gate did not return")
        gate_result = cpu.reg_read(UC_ARM_REG_R0)
    return parse_result, parsed_index, gate_result, writes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    parser.add_argument("rcx", type=Path)
    args = parser.parse_args()
    image = args.controller_segment.read_bytes()
    rcx = args.rcx.read_bytes()
    if hashlib.sha256(image).hexdigest() != SEGMENT_SHA256:
        parser.error("controller segment does not match XB22Q5")
    if hashlib.sha256(rcx).hexdigest() != RCX_SHA256:
        parser.error("RCX does not match XB22Q5")
    block = rcx.find(b"EPSONSIGNXB20d")
    if block != 0x112:
        parser.error("signature block is not at the expected position")
    original_header = rcx[block + 4096:block + 8192]
    if not original_header.startswith(b"EPSON IPLJ6XB"):
        parser.error("IPL header is not at the expected position")

    for index in (0, 1, 2, 3, 0x24, 0x25, 0xfe, 0xff):
        result, parsed_index, gate_result, writes = run_case(image, original_header, index)
        table_oob = [a for a, _ in writes if TABLE + TABLE_RECORDS * TABLE_RECORD_SIZE <= a < META]
        meta_oob = [a for a, _ in writes if a >= META + TABLE_RECORDS * META_RECORD_SIZE]
        key_overlap = [a for a, size in writes if a < SIGNATURE_BUFFER and a + size > KEY_BUFFER]
        print(f"index={index:#04x} result={result} parsed={parsed_index:#04x} "
              f"type_gate={gate_result if gate_result is not None else 'not_reached'} "
              f"table_write={hex(writes[0][0]) if writes else 'none'} "
              f"table_past_37={bool(table_oob)} meta_past_37={bool(meta_oob)} "
              f"key_buffer_overlap={bool(key_overlap)}")
        if index == 0x25 and not (result == 1 and table_oob and meta_oob and KEY_BUFFER in key_overlap):
            raise RuntimeError("expected out-of-range write was not reproduced")
        if index == 0x25 and gate_result != 0:
            raise RuntimeError("out-of-range record unexpectedly passed the reader's type gate")
        if index == 0xff and (result != 0 or writes):
            raise RuntimeError("sentinel control did not reject index 0xff")


if __name__ == "__main__":
    main()
