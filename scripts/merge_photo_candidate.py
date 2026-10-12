"""Merge verified UI CROM into the offline Wi-Fi/Telnet RCX candidate."""

import hashlib
from pathlib import Path
import struct
import argparse


from build_length_gate_candidate import record_integrity, records


BASE_HASH = "99bae21d9ac8bbba31271dc962414ac4262e9c097d91a58b8033f5747d788249"
CROM_OFFSET = 0x16DA122
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("base_rcx", type=Path)
parser.add_argument("source_crom", type=Path)
parser.add_argument("replacement_crom", type=Path)
parser.add_argument("output_rcx", type=Path)
args = parser.parse_args()
if args.base_rcx.resolve() == args.output_rcx.resolve():
    parser.error("output must differ from base image")
base = bytearray(args.base_rcx.read_bytes())
if hashlib.sha256(base).hexdigest() != BASE_HASH:
    raise ValueError("unexpected Wi-Fi/Telnet candidate")
source = args.source_crom.read_bytes()
replacement = args.replacement_crom.read_bytes()
if len(source) != len(replacement) or base[CROM_OFFSET:CROM_OFFSET + len(source)] != source:
    raise ValueError("CROM input does not match pinned candidate")
base[CROM_OFFSET:CROM_OFFSET + len(source)] = replacement
rows = list(records(base, trailing_bytes=1))
assert len(rows) == 3
position, header, first, second = rows[2]
struct.pack_into("<H", base, position + 0x36, sum(second) & 0xFFFF)
base[position + 0x44:position + 0x58] = hashlib.sha1(
    second + hashlib.sha1(header[:14]).digest()
).digest()
checks = list(record_integrity(base, trailing_bytes=1))
if not all(all(row[1:]) for row in checks):
    raise ValueError(f"record checks failed: {checks}")
target = args.output_rcx
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(base)
print("path", target)
print("bytes", len(base))
print("sha256", hashlib.sha256(base).hexdigest())
print("record_checks", checks)
print("firmware_sent", False)
