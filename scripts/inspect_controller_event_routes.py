#!/usr/bin/env python3
"""Inspect two ARM event jump tables in the XB22Q5 controller segment.

The input is segment 0 from extract_controller_crom.py, not an RCX or a
printer connection. This reports static branch targets only.
"""

import argparse
import hashlib
import struct
from pathlib import Path


PROVISIONAL_BASE = 0x45670000
LOAD_BASE = PROVISIONAL_BASE - 0x8C
EXPECTED_SHA256 = "7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416"


def word_at_provisional(data: bytes, address: int) -> int:
    return struct.unpack_from("<I", data, address - PROVISIONAL_BASE)[0]


def word_at_runtime(data: bytes, address: int) -> int:
    return struct.unpack_from("<I", data, address - LOAD_BASE)[0]


def arm_branch_target(instruction: int, address: int) -> int:
    if (instruction >> 25) & 0b111 != 0b101:
        raise ValueError(f"Expected ARM branch at {address:#x}: {instruction:#x}")
    displacement = instruction & 0xFFFFFF
    if displacement & 0x800000:
        displacement -= 0x1000000
    return address + 8 + displacement * 4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_segment", type=Path)
    args = parser.parse_args()
    data = args.controller_segment.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        parser.error("Input is not the expected XB22Q5 controller segment 0")

    tables = (
        ("internal request", 0x45833F48, (0x41, 0x42)),
        ("setup event", 0x45914FA0, (0x1A,)),
    )
    for name, table, commands in tables:
        for command in commands:
            entry = word_at_provisional(data, table + command * 4)
            instruction = word_at_runtime(data, entry)
            branch = arm_branch_target(instruction, entry) if (instruction >> 25) & 0b111 == 0b101 else None
            if branch is not None:
                detail = f"branch -> {branch:#x}"
            else:
                next_instruction = word_at_runtime(data, entry + 4)
                next_branch = arm_branch_target(next_instruction, entry + 4)
                detail = f"instruction {instruction:#010x}; next call -> {next_branch:#x}"
            print(f"{name} {command:#04x}: table -> {entry:#x}, {detail}")


if __name__ == "__main__":
    main()
