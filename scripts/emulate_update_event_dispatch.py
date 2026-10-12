#!/usr/bin/env python3
"""Isolate XB22Q5 controller group 0x76 jump-table behavior.

Requires a separately extracted, hash-matched CROM segment and Unicorn.
The CROM bytes load 0x8c below the earlier provisional mapping. This never
contacts a printer and does not model its controller OS.
"""

import argparse
import hashlib
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE_UNMAPPED
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_R9, UC_ARM_REG_SP


PROVISIONAL_BASE = 0x45670000
LOAD_BASE = PROVISIONAL_BASE - 0x8C
SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"
ENTRY = 0x45809A04 - 0x8C
STACK = 0x20000000
EVENT = 0x10000000
HANDLERS = {
    6: 0x45809A14,
    7: 0x45809A24,
    8: 0x45809A2C,
    9: 0x45809A44,
}


def run_case(image: bytes, subcommand: int) -> str:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    map_start = LOAD_BASE & ~0xFFF
    cpu.mem_map(map_start, (len(image) + LOAD_BASE - map_start + 0xFFF) & ~0xFFF)
    cpu.mem_write(LOAD_BASE, image)
    cpu.mem_map(STACK, 0x1000)
    cpu.mem_map(EVENT, 0x1000)
    sp = STACK + 0x100
    cpu.mem_write(sp + 0x20, EVENT.to_bytes(4, "little"))
    cpu.mem_write(EVENT + 8, subcommand.to_bytes(2, "little"))
    cpu.reg_write(UC_ARM_REG_SP, sp)
    cpu.reg_write(UC_ARM_REG_R9, 0x12345678)
    result = []

    def on_code(uc: Uc, address: int, size: int, user_data: object) -> None:
        if address == HANDLERS[subcommand]:
            result.append(f"selected handler {address:#x} "
                          f"(file offset {address - LOAD_BASE:#x})")
            uc.emu_stop()

    def on_bad_write(uc: Uc, access: int, address: int, size: int, value: int, user_data: object) -> bool:
        result.append(f"unmapped {size}-byte write to {address:#x} of {value:#x}")
        return False

    cpu.hook_add(UC_HOOK_CODE, on_code)
    cpu.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, on_bad_write)
    try:
        cpu.emu_start(ENTRY, 0, count=40)
    except UcError:
        if not result:
            raise
    return result[0] if result else "stopped without a classified result"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    args = parser.parse_args()
    image = args.controller_segment.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA256:
        parser.error("input is not the expected XB22Q5 controller segment 0")
    for subcommand in (6, 7, 8, 9):
        print(f"subcommand {subcommand}: {run_case(image, subcommand)}")


if __name__ == "__main__":
    main()
