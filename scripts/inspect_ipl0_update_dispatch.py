"""Recover the first IPL's update callback table from its startup copy map.

This is an offline check of the extracted XB22Q5 first IPL. It does not
establish which boot status or mode occurs on a physical printer.
"""

import argparse
import hashlib
from pathlib import Path
import struct


EXPECTED_SHA256 = "bf046b5bd5f5499c377bcbcb7b27aeb7d298cdf897600123f3f613bb8d2b7903"
COPY_DESCRIPTOR = 0x2EDC
TABLE_RUNTIME = 0x463297AC


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipl0", type=Path, help="extracted first IPL code image")
    args = parser.parse_args()
    image = args.ipl0.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"unexpected IPL SHA-256: {digest}")

    def word(offset: int) -> int:
        return struct.unpack_from("<I", image, offset)[0]

    def arm_branch_target(offset: int) -> int:
        instruction = word(offset)
        if (instruction >> 25) & 0x7 != 0x5:
            raise ValueError(f"expected ARM branch at {offset:#x}")
        displacement = instruction & 0xFFFFFF
        if displacement & 0x800000:
            displacement -= 0x1000000
        return offset + 8 + displacement * 4

    source, destination, length = struct.unpack_from("<III", image, COPY_DESCRIPTOR)
    if (source, destination, length) != (0x8010, 0x46309000, 0x22A1C):
        raise ValueError("unexpected first IPL startup copy descriptor")

    def from_runtime(address: int) -> int:
        if not destination <= address < destination + length:
            raise ValueError(f"address outside copied IPL region: {address:#x}")
        return source + address - destination

    if word(0x92D4) != TABLE_RUNTIME or word(0x9B60) != 0x463297D8:
        raise ValueError("unexpected callback-table literals")
    table = from_runtime(TABLE_RUNTIME)
    expected = (3, 0x4630A2EC, 0x4630A344, 0x4630A604)
    observed = tuple(word(table + index * 4) for index in range(4))
    if observed != expected:
        raise ValueError(f"unexpected update callback entries: {observed!r}")
    if tuple(from_runtime(value) for value in observed[1:]) != (0x92FC, 0x9354, 0x9614):
        raise ValueError("callback targets did not map to analyzed IPL functions")
    if arm_branch_target(0xB18) != 0xD58 or arm_branch_target(0xB20) != 0xB5C:
        raise ValueError("unexpected early boot-mode branch")
    if arm_branch_target(0xB58) != 0x3108 or word(0x3108) != 0xE51FF004:
        raise ValueError("unexpected early boot trampoline")
    if from_runtime(word(0x310C)) != 0x85EC:
        raise ValueError("boot trampoline does not enter first IPL update routine")
    if arm_branch_target(0x8624) != 0x8F60:
        raise ValueError("first IPL update entry does not call its dispatcher")

    print(f"IPL SHA-256: {digest}")
    print(f"Startup copy: {source:#x} -> {destination:#x}, {length:#x} bytes")
    print(f"Update callback table: RAM {TABLE_RUNTIME:#x} <- IPL {table:#x}")
    print("  +0x04 -> IPL 0x92fc (initialize update state)")
    print("  +0x08 -> IPL 0x9354 (prepare update state)")
    print("  +0x0c -> IPL 0x9614 (conditional signed-image finalizer)")
    print("Boot branch: 0xb18 mode decision -> 0xb58 trampoline -> 0x85ec -> 0x8f60")
    print("A zero mode-decision result skips the trampoline at 0xb20.")
    print("The table proves the indirect target, not its live boot status or mode.")


if __name__ == "__main__":
    main()
