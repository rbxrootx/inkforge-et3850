"""Create an offline candidate that keeps the Wi-Fi USB device awake.

Input: the extracted XB22Q5 /opt/nwsoc/wlan_enable_suspend.sh.
The output is not a flashable image or an installation package.
"""
import argparse
import hashlib
from pathlib import Path


EXPECTED = 'dd63b11cade9a72a570e9fe28d680456b5dfed51530a34d25f28acd55e93322a'
REPLACEMENTS = (
    (b'echo auto > /sys/bus/usb/devices/$dev_port/power/control',
     b'echo on > /sys/bus/usb/devices/$dev_port/power/control'),
    (b'echo 0 > /proc/net/rtl8821cu/wlan0/auto_suspend_block',
     b'echo 1 > /proc/net/rtl8821cu/wlan0/auto_suspend_block'),
    (b'echo 0 > /proc/net/rtl8723du/wlan0/auto_suspend_block',
     b'echo 1 > /proc/net/rtl8723du/wlan0/auto_suspend_block'),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.input.read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        parser.error('Unexpected source script SHA-256')
    patched = source
    for old, new in REPLACEMENTS:
        if patched.count(old) != 1:
            parser.error(f'Expected exactly one occurrence of {old!r}')
        patched = patched.replace(old, new, 1)
    args.output.write_bytes(patched)
    print('Candidate SHA-256:', hashlib.sha256(patched).hexdigest())


if __name__ == '__main__':
    main()
