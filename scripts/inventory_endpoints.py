"""List endpoint-shaped strings in a locally obtained firmware or updater binary.

This scans only the file supplied by the caller and never contacts a printer.
"""

import argparse
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('inputs', nargs='+', type=Path, help='Locally obtained binaries')
args = parser.parse_args()

ascii_strings = re.compile(rb'[ -~]{6,260}')
wide_strings = re.compile(rb'(?:[ -~]\x00){6,260}')
local_path = re.compile(
    r'^/(?:PRESENTATION|PRESENTATIONEX|FIRMWAREUPDATE|DOWN/FIRMWAREUPDATE|'
    r'Epson_WS_Config|WSD|config/|firmwareupdate/|update\.cgi|cgi_page_down)',
    re.IGNORECASE,
)
epson_url = re.compile(r'^https?://[^/]*\bepson\.[^/]+/', re.IGNORECASE)

for path in args.inputs:
    data = path.read_bytes()
    matches = set()
    for pattern, encoding in ((ascii_strings, 'ascii'), (wide_strings, 'utf-16le')):
        for hit in pattern.finditer(data):
            value = hit.group().decode(encoding)
            if local_path.search(value) or (
                epson_url.search(value)
                and not value.lower().startswith(('http://schemas.', 'https://schemas.'))
            ):
                matches.add((hit.start(), encoding, value))
    print(f'# {path} ({len(matches)} matches)')
    for offset, encoding, value in sorted(matches):
        print(f'0x{offset:08x}\t{encoding}\t{value}')
