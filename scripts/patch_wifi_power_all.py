"""Build an offline ET-3850 Wi-Fi power candidate for both Realtek paths.

The result is a modified nwsoc executable, not a flashable firmware image.
"""

import argparse
import hashlib
from pathlib import Path


EXPECTED_SHA256 = "70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0"
OLD = b"rtw_power_mgnt=1 rtw_enusbss=1"
NEW = b"rtw_power_mgnt=0 rtw_enusbss=0"
EXPECTED_DRIVERS = {"8723du.ko": 1, "8821cu.ko": 4}


def patch(source: bytes) -> tuple[bytes, list[tuple[int, str]]]:
    digest = hashlib.sha256(source).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"unexpected nwsoc SHA-256: {digest}")

    changes: list[tuple[int, str]] = []
    patched = bytearray(source)
    counts = {driver: 0 for driver in EXPECTED_DRIVERS}
    cursor = 0
    for item in source.split(b"\0"):
        if item.startswith(b"/sbin/insmod ") and OLD in item:
            drivers = [name for name in EXPECTED_DRIVERS if name.encode() in item]
            if len(drivers) != 1 or item.count(OLD) != 1:
                raise ValueError(f"unexpected insmod command at 0x{cursor:x}")
            driver = drivers[0]
            counts[driver] += 1
            offset = cursor + item.index(OLD)
            patched[offset : offset + len(OLD)] = NEW
            changes.append((offset, driver))
        cursor += len(item) + 1

    if counts != EXPECTED_DRIVERS:
        raise ValueError(f"unexpected driver command counts: {counts}")
    if len(source) != len(patched):
        raise AssertionError("patch changed file length")
    if sum(a != b for a, b in zip(source, patched)) != 2 * len(changes):
        raise AssertionError("patch changed bytes outside the expected digits")
    return bytes(patched), changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = args.input.read_bytes()
    candidate, changes = patch(source)
    args.output.write_bytes(candidate)
    for offset, driver in changes:
        print(f"0x{offset:x}: {driver}")
    print("Candidate SHA-256:", hashlib.sha256(candidate).hexdigest())


if __name__ == "__main__":
    main()
