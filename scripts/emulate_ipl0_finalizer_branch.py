"""Compare original and patched first-IPL positive-length branches in ARM emulation.

This isolates one basic block. It does not emulate boot ROM, flash staging, or
the entire first-IPL update sequence.
"""

import argparse
import hashlib
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM
from unicorn.arm_const import (
    UC_ARM_REG_FP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SL, UC_ARM_REG_SP,
)


IPL_SHA256 = "bf046b5bd5f5499c377bcbcb7b27aeb7d298cdf897600123f3f613bb8d2b7903"
IPL_IN_RCX = 0x4112
BRANCH = 0x97D0


def run(code: bytes) -> tuple[int, int, int]:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(0, 0x10000)
    cpu.mem_write(0, code[:0x10000])
    cpu.mem_map(0x500000, 0x1000)
    cpu.mem_map(0x600000, 0x1000)
    cpu.mem_write(0x500000, struct.pack("<I", 1))
    cpu.mem_write(0x500100, b"\x02")
    cpu.reg_write(UC_ARM_REG_FP, 0x500000)
    cpu.reg_write(UC_ARM_REG_SL, 0x500100)
    cpu.reg_write(UC_ARM_REG_SP, 0x600800)
    calls = {"error": 0, "ecdsa": 0}

    def hook(engine, address, size, _):
        if address == 0x8F3C:
            calls["error"] += 1
            engine.reg_write(UC_ARM_REG_PC, engine.reg_read(UC_ARM_REG_LR))
        elif address == 0xA2A0:
            calls["ecdsa"] += 1
            engine.reg_write(UC_ARM_REG_PC, engine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(0x97C8, 0x9804, count=30)
    if cpu.reg_read(UC_ARM_REG_PC) != 0x9804:
        raise AssertionError("finalizer block did not reach its end")
    state = cpu.mem_read(0x500100, 1)[0]
    return calls["error"], calls["ecdsa"], state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_ipl", type=Path)
    parser.add_argument("candidate_rcx", type=Path)
    args = parser.parse_args()
    original = args.original_ipl.read_bytes()
    candidate = args.candidate_rcx.read_bytes()[IPL_IN_RCX:]
    if hashlib.sha256(original).hexdigest() != IPL_SHA256:
        parser.error("unexpected original IPL image")
    if len(candidate) < 0x10000:
        parser.error("candidate RCX is too short")
    before = struct.unpack_from("<I", original, BRANCH)[0]
    after = struct.unpack_from("<I", candidate, BRANCH)[0]
    if (before, after) != (0x1A000007, 0x1A000009):
        parser.error("expected original and redirected BNE instructions")
    stock = run(original)
    patched = run(candidate)
    print("original: error_calls=%d ecdsa_calls=%d final_state=%d" % stock)
    print("patched:  error_calls=%d ecdsa_calls=%d final_state=%d" % patched)
    if stock != (1, 0, 3) or patched != (0, 0, 3):
        raise AssertionError("unexpected isolated finalizer behavior")
    print("Only the local positive-count branch is established; no printer contact was made.")


if __name__ == "__main__":
    main()
