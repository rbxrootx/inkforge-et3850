"""Check whether the bundled updater's generic key table covers XB22Q5.

Requires the third-party cryptography package. The offsets and SHA-256 below
apply only to EPFWUPD.exe bundled with Epson's XB22Q5 recovery package.
"""
import argparse
import fnmatch
import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


UPDATER_SHA256 = "ff3694753ea409d5a6d0b98c1c6b29afb8e8c6ca520fc9a04d2ceec520863f74"
PATTERN_OFFSET = 0x25F564
KEY_OFFSET = 0x25F678
STRIDE = 0x158
ENTRY_COUNT = 47


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("updater", type=Path)
    parser.add_argument("rcx", type=Path)
    args = parser.parse_args()
    updater = args.updater.read_bytes()
    if hashlib.sha256(updater).hexdigest() != UPDATER_SHA256:
        raise SystemExit("Unexpected updater version; key table offsets may differ")
    image = args.rcx.read_bytes()
    marker = image.find(b"EPSONSIGNXB20d")
    if marker < 0:
        raise SystemExit("XB20d signature block missing")
    payload = image[marker + 4096 :]
    if len(payload) != int.from_bytes(image[marker + 16 : marker + 20], "little"):
        raise SystemExit("Signed payload length mismatch")
    sig = image[marker + 32 : marker + 96]
    der = utils.encode_dss_signature(int.from_bytes(sig[:32], "big"),
                                     int.from_bytes(sig[32:], "big"))
    digest = hashlib.sha256(payload).digest()
    version = "05.15.XB22Q5.FY20"
    filename_matches = []
    signature_matches = []
    for index in range(ENTRY_COUNT):
        pattern_start = PATTERN_OFFSET + index * STRIDE
        pattern = updater[pattern_start : pattern_start + 128].split(b"\0")[0].decode("ascii")
        key_start = KEY_OFFSET + index * STRIDE
        raw = updater[key_start : key_start + 64]
        if fnmatch.fnmatchcase(version, pattern.split(",")[0]):
            filename_matches.append((index, pattern))
        try:
            key = ec.EllipticCurvePublicNumbers(
                int.from_bytes(raw[:32], "big"),
                int.from_bytes(raw[32:], "big"), ec.SECP256R1()).public_key()
            key.verify(der, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
            signature_matches.append((index, pattern))
        except (ValueError, InvalidSignature):
            pass
    print(f"checked {ENTRY_COUNT} generic key-table entries for {version}")
    print(f"filename pattern matches: {filename_matches}")
    print(f"signature-verifying keys: {signature_matches}")
    print("This does not rule out other updater or device verification paths.")


if __name__ == "__main__":
    main()
