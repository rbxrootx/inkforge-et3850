"""Offline control-flow test for XB22Q5 package reader length handling.

The real ARM code for the signature-header parser, stream counter, package
header parser, and three-record reader executes. Hardware I/O, hashing,
record checksum/SHA1 checks, and staging operations are stubbed. Thus this
isolates the signature *control-flow* question, not complete image validity.
"""
import hashlib
import argparse
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_SP)

PROVISIONAL_BASE = 0x45670000
LOAD_BASE = PROVISIONAL_BASE - 0x8c
DELTA = PROVISIONAL_BASE - LOAD_BASE
STOP = 0x14000000
CALLBACK = 0x15000000
STACK = 0x10000000
BUFFER = 0x12000000
STORAGE = 0x13000000


def run(controller: bytes, rcx: bytes, declared_length: int):
    sign = rcx.index(b'EPSONSIGNXB20d')
    actual = len(rcx) - sign - 4096
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    map_start = LOAD_BASE & ~0xfff
    cpu.mem_map(map_start, (len(controller) + LOAD_BASE - map_start + 0xfff) & ~0xfff)
    cpu.mem_write(LOAD_BASE, controller)
    for addr, length in ((0x43ea0000, 0x20000), (0x45c00000, 0x200000),
                         (0x4fb26000, 0x2000), (STACK, 0x10000),
                         (BUFFER, 0x2000), (STORAGE, 0x1000),
                         (STOP, 0x1000), (CALLBACK, 0x1000)):
        cpu.mem_map(addr, length)
    candidate = bytearray(rcx[sign:])
    struct.pack_into('<I', candidate, 16, declared_length)
    state = {'cursor': 0, 'verify': 0, 'checksum': 0, 'sha1': 0, 'reads': []}

    def ret(uc, value=1):
        uc.reg_write(UC_ARM_REG_R0, value)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def hook(uc, address, size, user):
        if address == STOP:
            uc.emu_stop()
            return
        r0 = uc.reg_read(UC_ARM_REG_R0)
        r1 = uc.reg_read(UC_ARM_REG_R1)
        r2 = uc.reg_read(UC_ARM_REG_R2)
        r3 = uc.reg_read(UC_ARM_REG_R3)
        if address == CALLBACK:
            ret(uc, 0)
        elif address == 0x458ac684 - DELTA:
            uc.mem_write(r3, struct.pack('<I', BUFFER))
            ret(uc)
        elif address == 0x458acd14 - DELTA:
            ret(uc)
        elif address == 0x45778224 - DELTA:
            cursor = state['cursor']
            assert cursor + r2 <= len(candidate), (cursor, r2, len(candidate))
            if r2 <= 4096:
                uc.mem_write(r1, bytes(candidate[cursor:cursor + r2]))
            state['cursor'] += r2
            state['reads'].append((cursor, r2))
            ret(uc)
        elif address == 0x45a227c4 - DELTA:
            same = uc.mem_read(r0, r2) == uc.mem_read(r1, r2)
            ret(uc, 0 if same else 1)
        elif address == 0x458b0930 - DELTA:
            uc.mem_write(r0, bytes(uc.mem_read(r1, r2)))
            ret(uc, r0)
        elif address in (0x45778dbc - DELTA, 0x45778de4 - DELTA, 0x45778e18 - DELTA):
            ret(uc)
        elif address == 0x45778f0c - DELTA:
            state['verify'] += 1
            ret(uc, 0)
        elif address == 0x458aa35c - DELTA:
            uc.mem_write(r1, struct.pack('<H', 0x7fff))
            ret(uc)
        elif address == 0x458aa25c - DELTA:
            ret(uc)
        elif address == 0x45728a94 - DELTA:
            uc.mem_write(r0, struct.pack('<I', 0x1000000))
            ret(uc, STORAGE)
        elif address == 0x4577787c - DELTA:
            state['checksum'] += 1
            ret(uc)
        elif address == 0x45778d14 - DELTA:
            state['sha1'] += 1
            ret(uc)
        elif address in (0x45728d8c - DELTA, 0x45728dc4 - DELTA,
                        0x45728dfc - DELTA, 0x45728e34 - DELTA):
            ret(uc)

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
    cpu.reg_write(UC_ARM_REG_R0, CALLBACK)
    cpu.reg_write(UC_ARM_REG_R1, 0x0b)
    cpu.reg_write(UC_ARM_REG_LR, STOP)
    cpu.emu_start(0x45778404 - DELTA, STOP, count=1000000)
    assert cpu.reg_read(UC_ARM_REG_PC) == STOP
    result = cpu.reg_read(UC_ARM_REG_R0)
    counter = struct.unpack('<I', cpu.mem_read(0x43eac57c, 4))[0]
    return result, counter, state, actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('controller_segment', type=Path)
    parser.add_argument('rcx', type=Path)
    parser.add_argument('--compare-plus-one', action='store_true',
                        help='also try an in-memory length increment')
    args = parser.parse_args()
    controller = args.controller_segment.read_bytes()
    rcx = args.rcx.read_bytes()
    if hashlib.sha256(controller).hexdigest() != '7bdc1c0562adda78bb541cbadac1ac104367c0b839262ea1f51d38e07a54e416':
        parser.error('controller segment is not the pinned XB22Q5 build')
    sign = rcx.find(b'EPSONSIGNXB20d')
    if sign != 0x112:
        parser.error('expected XB20 signature block at 0x112')
    declared = struct.unpack_from('<I', rcx, sign + 16)[0]
    for length in (declared, declared + 1) if args.compare_plus_one else (declared,):
        result, remaining, evidence, actual = run(controller, rcx, length)
        print('declared', length, 'actual', actual,
              'reader_return', result, 'remaining', remaining,
              'verify_calls', evidence['verify'], 'checksum_calls', evidence['checksum'],
              'sha1_calls', evidence['sha1'], 'read_count', len(evidence['reads']))
    print('Record checksum/SHA1 results above are stubbed; validate them separately.')


if __name__ == '__main__':
    main()
