#!/usr/bin/env python3
"""Check the XB22Q5 secondary controller image's update-mode code offline."""

import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_SHA256 = "8a6fd7facdf4534eb4c5e4f4261700fb839880f006e3e0ce19dea44f1c977c9d"
BASE = 0x4343F000


def word(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - BASE)[0]


def arm_branch_target(image: bytes, address: int) -> int:
    instruction = word(image, address)
    if (instruction & 0x0E000000) != 0x0A000000:
        raise ValueError(f"No ARM branch at {address:#x}")
    displacement = instruction & 0xFFFFFF
    if displacement & 0x800000:
        displacement -= 0x1000000
    return address + 8 + displacement * 4


def inspect(path: Path) -> None:
    image = path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"Unexpected image SHA-256: {digest}")
    if len(image) != 0x140A20:
        raise ValueError(f"Unexpected image length: {len(image):#x}")

    labels = {
        0x434489C0: b"EPSON PRINTER\0",
        0x434489D0: b"Program Update Mode\0",
        0x434489E4: b"FINISHED MAIN\0",
        0x43448A00: b"ROM1 FIXSUM\0",
        0x43448A0C: b"ROM2 FIXSUM\0",
        0x43448A18: b"ROM3 FIXSUM\0",
    }
    for address, expected in labels.items():
        actual = image[address - BASE : address - BASE + len(expected)]
        if actual != expected:
            raise ValueError(f"Label mismatch at {address:#x}")

    if word(image, BASE + 0xE920C) != 0x434489C0:
        raise ValueError("Image mapping anchor does not resolve")

    branches = {
        0x43476778: 0x43476188,  # state dispatcher -> update command handler
        0x43476208: 0x43476010,  # command handler -> working-memory setup
        0x43444DB8: 0x435202D8,  # update dispatcher -> ROM programmer wrapper
        0x43444E3C: 0x435202D8,  # alternate update case
        0x4352032C: 0x43448A5C,  # initialization -> ROM programmer
        0x43448D54: 0x434487B8,  # ROM programmer -> finished display
        0x43448CCC: 0x43448788,  # ROM programmer -> byte-sum checker
    }
    for source, expected_target in branches.items():
        actual_target = arm_branch_target(image, source)
        if actual_target != expected_target:
            raise ValueError(f"Unexpected branch {source:#x} -> {actual_target:#x}")

    if word(image, 0x43448798) != 0xE4D0C001:
        raise ValueError("Byte load changed in checksum loop")
    if word(image, 0x434487A4) != 0xE083300C:
        raise ValueError("Byte addition changed in checksum loop")
    if word(image, 0x4347697C) != 0x43444BFC:
        raise ValueError("Working-memory dispatcher source changed")
    if word(image, 0x4346F780) != 0xE3A00003:
        raise ValueError("Command-status helper no longer returns 3")
    if word(image, 0x4346F78C) != 0xE3A00000:
        raise ValueError("Command-mode helper no longer returns 0")

    print(f"Image SHA-256: {digest}")
    print(f"Mapped ARM base: {BASE:#x}")
    print("Update-mode ROM programmer: 0x43448a5c")
    print("State/command chain: 0x434765f8 -> 0x43476188 -> 0x43476010")
    print("Dispatcher copied to working memory from 0x43444bfc")
    print("Local command gate helpers return constants 3 and 0")
    print("Post-program byte-sum routine: 0x43448788")
    print("Finished/status display: 0x434487b8")
    print("No network caller or signature bypass is established by these checks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decoded_segment", type=Path)
    inspect(parser.parse_args().decoded_segment)
