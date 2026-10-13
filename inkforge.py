"""Owner-operated ET-3850 firmware build and install workflow.

No Epson image or credentials are bundled. Only the exact XB22Q5 source is
supported. Build output and password remain outside this code repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import sys

from et3850 import ROOT, SOURCE_SHA256, inspect_firmware, sha256_file
from et3850_mod import build_candidate
from workdir import WORK_DIR

SCRIPT = ROOT / "scripts" / "inkforge_repack.sh"
PRIVATE_WORK = WORK_DIR
S0 = 0xEA7112
S1 = 0x1197112
EXPECTED_S0 = 2008372
EXPECTED_S1 = 2630538


def private_path(path: Path) -> Path:
    path = path.resolve()
    if PRIVATE_WORK.resolve() not in path.parents or ROOT in path.parents:
        raise ValueError("firmware outputs and passwords must stay in the configured work directory outside the repository")
    return path


def wsl_path(path: Path) -> str:
    path = path.resolve()
    drive, tail = os.path.splitdrive(str(path))
    if len(drive) != 2 or drive[1] != ":":
        raise ValueError(f"WSL cannot access {path}")
    return "/mnt/" + drive[0].lower() + tail.replace("\\", "/")


def image_slice(blob: bytes, offset: int, used: int) -> bytes:
    if blob[offset:offset + 4] != b"hsqs":
        raise ValueError(f"SquashFS magic absent at 0x{offset:x}")
    actual = struct.unpack_from("<Q", blob, offset + 40)[0]
    if actual != used or offset + actual > len(blob):
        raise ValueError(f"unexpected SquashFS size at 0x{offset:x}: {actual}")
    return blob[offset:offset + actual]


def build(source: Path, output: Path, password_file: Path, log=lambda line: None) -> dict:
    source = source.resolve()
    output = private_path(output)
    password_file = private_path(password_file)
    if source == output or output.exists():
        raise ValueError("choose a new output RCX path distinct from the source")
    if sha256_file(source) != SOURCE_SHA256:
        raise ValueError("source must be the pinned XB22Q5 RCX")
    secret_created = False
    if password_file.exists():
        secret = password_file.read_bytes().strip()
        if len(secret) < 24 or b"\r" in secret or b"\n" in secret:
            raise ValueError("existing password file must hold one line of at least 24 bytes")
    else:
        password_file.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_urlsafe(32).encode("ascii")
        with password_file.open("xb") as stream:
            stream.write(secret + b"\n")
        secret_created = True
    # Never print the password or embed it in the manifest.
    work = output.with_suffix(".build")
    work.mkdir(parents=True, exist_ok=True)
    source_bytes = source.read_bytes()
    first = work / "stock-root.squashfs"
    second = work / "stock-network.squashfs"
    first.write_bytes(image_slice(source_bytes, S0, EXPECTED_S0))
    second.write_bytes(image_slice(source_bytes, S1, EXPECTED_S1))
    out0 = work / "mod-root.squashfs"
    out1 = work / "mod-network.squashfs"
    command = ["wsl", "-u", "root", "--", "bash", wsl_path(SCRIPT), wsl_path(first), wsl_path(second),
               wsl_path(password_file), wsl_path(out0), wsl_path(out1)]
    log("Repacking pinned Linux filesystems in WSL")
    process = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if process.returncode:
        raise RuntimeError("WSL repack failed: " + (process.stderr or process.stdout)[-2500:])
    log(process.stdout.strip())
    log("Building checked RCX container")
    result = build_candidate(source, out1, output, first_squashfs=out0)
    if result["returncode"]:
        raise RuntimeError("RCX build failed: " + (result["stderr"] or result["stdout"])[-2500:])
    report = inspect_firmware(output)
    if (len(report["records"]) != 3 or
        not all(all(record[key] for key in ("first_sum_ok", "second_sum_ok", "sha1_ok"))
                for record in report["records"]) or
        report["trailing_bytes_after_records"] != 1 or
        report["signature_block"]["length_delta"] != 0 or
        report["embedded_signature"] != "invalid for embedded key"):
        output.unlink(missing_ok=True)
        raise RuntimeError("built RCX failed post-build integrity checks")
    manifest = {
        "schema": "inkforge-et3850-v1", "model": "ET-3850", "firmware": "XB22Q5",
        "source_sha256": SOURCE_SHA256, "image_sha256": report["sha256"],
        "image_bytes": report["bytes"], "first_squashfs_sha256": sha256_file(out0),
        "second_squashfs_sha256": sha256_file(out1),
        "modifications": ["password-gated root shell on TCP 2323", "Wi-Fi power management disabled"],
        "password_file": str(password_file), "password_created": secret_created,
        "signature_status": report["embedded_signature"],
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log("Built " + report["sha256"])
    return {"image": str(output), "manifest": str(manifest_path), **manifest}


def postflight(host: str, password_file: Path) -> dict:
    from mod_shell import connect
    command = ("id; uname -a; md5sum /opt/nwsoc/nwsoc; "
               "cat /sys/module/8723du/parameters/rtw_power_mgnt; "
               "cat /sys/module/8723du/parameters/rtw_enusbss")
    return connect(host, password_file, command)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("source", type=Path)
    build_parser.add_argument("output", type=Path)
    build_parser.add_argument("--password-file", type=Path, required=True)
    install_parser = sub.add_parser("install")
    install_parser.add_argument("image", type=Path)
    install_parser.add_argument("--send", action="store_true")
    status_parser = sub.add_parser("postflight")
    status_parser.add_argument("host")
    status_parser.add_argument("--password-file", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "build":
        result = build(args.source, args.output, args.password_file, print)
    elif args.action == "install":
        from usb_update import transfer
        result = transfer(args.image, args.send, manifest=args.image.with_suffix(args.image.suffix + ".manifest.json"))
    else:
        result = postflight(args.host, args.password_file)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
