#!/usr/bin/env python3
"""Check XB22Q5 package record sums and SHA-1 digests offline."""

import argparse
from pathlib import Path

from build_length_gate_candidate import PAYLOAD_OFFSET, record_integrity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rcx', type=Path)
    parser.add_argument('--trailing-byte', action='store_true')
    args = parser.parse_args()
    image = args.rcx.read_bytes()
    if image[0x112:0x120] != b'EPSONSIGNXB20d':
        parser.error('expected XB20 signature header')
    declared = int.from_bytes(image[0x122:0x126], 'little')
    actual = len(image) - PAYLOAD_OFFSET
    results = list(record_integrity(image, int(args.trailing_byte)))
    for position, first_sum, second_sum, sha1 in results:
        print(f'record={position:#x} first_sum_ok={first_sum} '
              f'second_sum_ok={second_sum} sha1_ok={sha1}')
    print(f'declared={declared} actual={actual} trailing={int(args.trailing_byte)}')
    if not all(first_sum and second_sum and sha1
               for _, first_sum, second_sum, sha1 in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
