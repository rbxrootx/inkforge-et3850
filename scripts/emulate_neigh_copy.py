"""Exercise XB22Q5 nwsoc's ARM ip-neigh parser with synthetic command output.

Install Unicorn separately (`python -m pip install unicorn`). This harness
stubs libc calls and never contacts the printer.
"""

import argparse
import hashlib
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP)


START = 0x00580EE8
END = 0x30000000
STACK = 0x20000000
DATA = 0x10000000
DEST = DATA + 0x100
MAC = DATA + 0x200
FAKE_FILE = DATA + 0x300
EXPECTED_SHA256 = "70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0"


def cstr(cpu, addr, max_len=2048):
    raw = bytes(cpu.mem_read(addr, max_len))
    return raw.split(b"\x00", 1)[0]


def run(image, address):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(0x10000, 0x800000)
    cpu.mem_write(0x10000, image)
    cpu.mem_map(STACK, 0x20000)
    cpu.mem_map(DATA, 0x1000)
    cpu.mem_map(END, 0x1000)
    cpu.mem_write(DEST, b"\x00" * 16 + b"Z" * 64)
    cpu.mem_write(MAC, b"aa:bb:cc:dd:ee:ff\x00")
    cpu.reg_write(UC_ARM_REG_R0, DEST)
    cpu.reg_write(UC_ARM_REG_R1, MAC)
    cpu.reg_write(UC_ARM_REG_SP, STACK + 0x1F000)
    cpu.reg_write(UC_ARM_REG_LR, END)
    line = (address + " dev p2p0 lladdr aa:bb:cc:dd:ee:ff REACHABLE\n").encode()
    calls = []
    first_token = None
    finished = []

    def r(reg):
        return cpu.reg_read(reg)

    def watch(uc, pc, size, user_data):
        nonlocal first_token
        if pc == END:
            finished.append(True)
            uc.emu_stop()
            return
        if pc in (0x580F0C, 0x580F2C, 0x580FE8):  # printf/puts
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == 0x580F18:  # popen("ip neigh", "r")
            assert cstr(uc, r(UC_ARM_REG_R0)) == b"ip neigh"
            uc.reg_write(UC_ARM_REG_R0, FAKE_FILE)
        elif pc == 0x580F4C:  # fgets
            assert len(line) + 1 <= r(UC_ARM_REG_R1)
            uc.mem_write(r(UC_ARM_REG_R0), line + b"\x00")
        elif pc == 0x580F70:  # strstr
            hay = cstr(uc, r(UC_ARM_REG_R0))
            needle = cstr(uc, r(UC_ARM_REG_R1))
            pos = hay.find(needle)
            uc.reg_write(UC_ARM_REG_R0,
                         (r(UC_ARM_REG_R0) + pos) if pos >= 0 else 0)
        elif pc == 0x580F98:  # strtok
            buf = r(UC_ARM_REG_R0)
            raw = cstr(uc, buf)
            token = raw.split(b" ", 1)[0]
            uc.mem_write(buf + len(token), b"\x00")
            first_token = token
            uc.reg_write(UC_ARM_REG_R0, buf)
        elif pc in (0x580FA8, 0x580FC4):  # strlen
            uc.reg_write(UC_ARM_REG_R0, len(cstr(uc, r(UC_ARM_REG_R0))))
        elif pc == 0x580FBC:  # strncpy: capture the actual ARM arguments
            dst, src, n = r(UC_ARM_REG_R0), r(UC_ARM_REG_R1), r(UC_ARM_REG_R2)
            calls.append((dst, src, n))
            uc.mem_write(dst, bytes(uc.mem_read(src, n)))
            uc.reg_write(UC_ARM_REG_R0, dst)
        elif pc == 0x580FF4:  # feof: not expected for a matching line
            raise RuntimeError("Unexpected feof branch")
        elif pc == 0x581008:  # pclose
            uc.reg_write(UC_ARM_REG_R0, 0)
        else:
            return
        uc.reg_write(UC_ARM_REG_PC, pc + 4)

    cpu.hook_add(UC_HOOK_CODE, watch)
    cpu.emu_start(START, END, count=1000)
    if (not finished and cpu.reg_read(UC_ARM_REG_PC) != END) or len(calls) != 1:
        raise RuntimeError("Parser did not finish one matching line: pc=%x calls=%s" %
                           (cpu.reg_read(UC_ARM_REG_PC), calls))
    dest, src, n = calls[0]
    return {
        "input": address,
        "token_length": len(first_token),
        "strncpy_length": n,
        "destination_is_16_byte_buffer": dest == DEST,
        "copy_matches_token": bytes(cpu.mem_read(DEST, n)) == first_token,
        "byte_after_buffer": bytes(cpu.mem_read(DEST + 16, 1)).hex(),
        "terminator_offset": n,
        "guard_intact": bytes(cpu.mem_read(DEST + 16, 64)) == b"Z" * 64,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nwsoc", type=Path, help="separately extracted XB22Q5 ARM program")
    args = parser.parse_args()
    image = args.nwsoc.read_bytes()
    if hashlib.sha256(image).hexdigest() != EXPECTED_SHA256:
        parser.error("Not the expected XB22Q5 nwsoc image")
    for addr in ("192.0.2.12", "2001:db8:0::abcd",
                 "2001:db8:dead:beef:1234:5678:9abc:def0"):
        print(run(image, addr))


if __name__ == "__main__":
    main()
