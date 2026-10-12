"""Extract and verify Epson's official XB22Q5 package without redistributing it."""
import argparse
import hashlib
from io import BytesIO
from pathlib import Path
import re
import struct
from zipfile import ZipFile

EXPECTED_EXE = 'e12cb391e4473391115d6e4c5d8dc3c9bd1e3ca78727a5cbb79370947a50d731'
EXPECTED_RCX = '103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675'

parser = argparse.ArgumentParser()
parser.add_argument('--package', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
exe = args.package.read_bytes()
assert hashlib.sha256(exe).hexdigest() == EXPECTED_EXE, 'Unexpected EXE hash'
with ZipFile(BytesIO(exe)) as outer:
    efu = outer.read('FWCJ61TL/FWCJ61TL.efu')
with ZipFile(BytesIO(efu)) as inner:
    rcx = inner.read('FWCJ61TL.rcx')
assert hashlib.sha256(rcx).hexdigest() == EXPECTED_RCX, 'Unexpected RCX hash'
args.output.mkdir(parents=True, exist_ok=True)
(args.output / 'FWCJ61TL.rcx').write_bytes(rcx)
count = 0
for count, match in enumerate(re.finditer(b'hsqs', rcx), start=1):
    offset = match.start()
    bytes_used = struct.unpack_from('<Q', rcx, offset + 40)[0]
    assert 0 < bytes_used <= len(rcx) - offset
    path = args.output / ('squashfs_%d.img' % (count - 1))
    path.write_bytes(rcx[offset:offset + bytes_used])
    print(path, 'offset', hex(offset), 'size', bytes_used)
assert count == 2, 'Expected exactly two SquashFS images'
