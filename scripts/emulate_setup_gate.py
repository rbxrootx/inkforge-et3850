#!/usr/bin/env python3
"""Run the XB22Q5 controller's 32-byte setup gate in Unicorn.

This exercises one function from the separately extracted ARM image. It does
not emulate the controller OS, the network stack, or an update operation.
Install Unicorn separately (`python -m pip install unicorn`).
"""

import argparse
import hashlib
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC


BASE = 0x45670000
FUNCTION = 0x4591465C
SETUP_REQUEST = 0x4589B0FC
END = 0x30000000
DATA = 0x10000000
STACK = 0x20000000
IMAGE_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"


def run_case(image: bytes, payload: bytes) -> str:
    if len(payload) < 32:
        payload += b"\x00"
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(BASE, (len(image) + 0xFFF) & ~0xFFF)
    cpu.mem_write(BASE, image)
    cpu.mem_map(DATA, 0x1000)
    cpu.mem_map(STACK, 0x1000)
    cpu.mem_map(END, 0x1000)
    cpu.mem_write(DATA, b"\x00" * 12 + (DATA + 0x100).to_bytes(4, "little") + b"\x00" * 4)
    cpu.mem_write(DATA + 0x100, payload)
    cpu.reg_write(UC_ARM_REG_R0, DATA)
    cpu.reg_write(UC_ARM_REG_SP, STACK + 0xFF0)
    cpu.reg_write(UC_ARM_REG_LR, END)
    reached = []

    def watch(uc, address, size, user_data):
        if address in (SETUP_REQUEST, END):
            reached.append(address)
            uc.emu_stop()

    cpu.hook_add(UC_HOOK_CODE, watch)
    cpu.emu_start(FUNCTION, END, count=300)
    if not reached and cpu.reg_read(UC_ARM_REG_PC) == END:
        reached.append(END)
    if not reached:
        raise RuntimeError("Function did not reach the setup request or return")
    return "accepted" if reached[0] == SETUP_REQUEST else "rejected"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    args = parser.parse_args()
    image = args.controller_segment.read_bytes()
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        parser.error("Input is not the expected XB22Q5 controller segment 0")
    cases = {
        "IPPRes prefix": b"IPPRes:200\r\n" + b"A" * 32,
        "31 base64 characters": b"A" * 31,
        "32 base64 characters": b"A" * 32,
    }
    for label, payload in cases.items():
        print(f"{label}: {run_case(image, payload)}")


if __name__ == "__main__":
    main()
