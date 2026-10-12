"""Check an RCX signature against the key in the currently installed IPL image.

This models the key input to the mapped first-IPL P-256 verifier. It does not
execute printer firmware or establish which update route invokes that verifier.
"""

import argparse
import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trusted_ipl", type=Path, help="raw code image of the running first IPL")
    parser.add_argument("candidate_rcx", type=Path)
    args = parser.parse_args()
    boot = args.trusted_ipl.read_bytes()
    rcx = args.candidate_rcx.read_bytes()
    if len(boot) < 0x7050 or len(rcx) < 0x1112 or rcx[0x112:0x120] != b"EPSONSIGNXB20d":
        raise ValueError("unexpected IPL or XB20 RCX layout")
    key = boot[0x7010:0x7050]
    public = ec.EllipticCurvePublicNumbers(
        int.from_bytes(key[:32], "big"), int.from_bytes(key[32:], "big"), ec.SECP256R1()
    ).public_key()
    raw_signature = rcx[0x132:0x172]
    signature = utils.encode_dss_signature(
        int.from_bytes(raw_signature[:32], "big"),
        int.from_bytes(raw_signature[32:], "big"),
    )
    digest = hashlib.sha256(rcx[0x1112:]).digest()
    try:
        public.verify(signature, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    except InvalidSignature:
        print("RCX signature REJECTED by the running IPL image's public key.")
    else:
        print("RCX signature accepted by the running IPL image's public key.")
    print("Running IPL key SHA-256:", hashlib.sha256(key).hexdigest())
    print("Candidate embedded key SHA-256:", hashlib.sha256(rcx[0xB122:0xB162]).hexdigest())


if __name__ == "__main__":
    main()
