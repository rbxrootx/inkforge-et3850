"""Photo/Wi-Fi/Telnet workbench entry point for the owner's ET-3850."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from et3850 import (ASSETS, ROOT, SCRIPTS, SOURCE_SHA256, VID_PID,
                    inspect_firmware, printer_queues, sha256_file,
                    tcp_services, usb_bulk_interface, usb_devices)


def build_candidate(original: Path, squashfs: Path, output: Path,
                    append_byte: bool = True, patch_ipl: bool = True,
                    first_squashfs: Path | None = None) -> dict:
    """Run the checked offline builder with both optional SquashFS images."""
    original, squashfs, output = (path.resolve() for path in (original, squashfs, output))
    if original == output or squashfs == output:
        raise ValueError("output must differ from each input")
    if ROOT in output.parents or output == ROOT:
        raise ValueError("firmware output must remain outside the research repository")
    if sha256_file(original) != SOURCE_SHA256:
        raise ValueError("source is not the pinned XB22Q5 RCX")
    command = [sys.executable, str(SCRIPTS / "build_length_gate_candidate.py"),
               str(original), str(squashfs), str(output)]
    if first_squashfs:
        first_squashfs = first_squashfs.resolve()
        if first_squashfs == output:
            raise ValueError("first SquashFS input and RCX output must differ")
        command.extend(["--replacement-first-squashfs", str(first_squashfs)])
    if append_byte:
        command.append("--append-byte")
    if patch_ipl:
        command.append("--patch-ipl-finalizer")
    process = subprocess.run(command, capture_output=True, text=True, timeout=180)
    return {"returncode": process.returncode, "stdout": process.stdout,
            "stderr": process.stderr, "output": str(output) if process.returncode == 0 else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="launch the graphical workbench")
    sub.add_parser("status", help="read local USB and printer queue metadata")
    usb_status = sub.add_parser("usb-status", help="read live D4 version and status")
    usb_status.add_argument("--winusb", action="store_true")
    inspect = sub.add_parser("inspect", help="inspect an RCX offline")
    inspect.add_argument("rcx", type=Path)
    build = sub.add_parser("build", help="build the offline Wi-Fi/Telnet candidate")
    build.add_argument("source_rcx", type=Path)
    build.add_argument("replacement_squashfs", type=Path)
    build.add_argument("output_rcx", type=Path)
    build.add_argument("--first-squashfs", type=Path)
    build.add_argument("--no-append-byte", action="store_true")
    build.add_argument("--no-ipl-patch", action="store_true")
    flash = sub.add_parser("flash", help="hash-locked RCX preflight; --send contacts the printer")
    flash.add_argument("rcx", type=Path)
    flash.add_argument("--send", action="store_true")
    flash.add_argument("--transport", choices=("usbprint", "winusb"), default="usbprint")
    services = sub.add_parser("services", help="probe TCP 22, 23, and custom shell 2323")
    services.add_argument("host")
    shell = sub.add_parser("shell", help="log in to the installed password-gated root shell")
    shell.add_argument("host")
    shell.add_argument("--password-file", type=Path,
                       default=ROOT.parent.parent / "work" / "telnet_password.txt")
    shell.add_argument("--command", dest="shell_command",
                       help="run one shell command instead of an interactive session")
    args = parser.parse_args()
    if args.command in (None, "gui"):
        from et3850_gui import run
        run()
        return
    if args.command == "status":
        result = {"usb": usb_devices(), "queues": printer_queues(),
                  "winusb": usb_bulk_interface(),
                  "update_transport": "custom image installed; private port 2323 returned uid=0(root); Wi-Fi power parameters 0/0 verified live"}
    elif args.command == "usb-status":
        from usb_d4 import read_identity
        result = read_identity(args.winusb)
    elif args.command == "inspect":
        result = inspect_firmware(args.rcx)
    elif args.command == "build":
        result = build_candidate(args.source_rcx, args.replacement_squashfs, args.output_rcx,
                                 not args.no_append_byte, not args.no_ipl_patch,
                                 args.first_squashfs)
    elif args.command == "flash":
        from usb_update import transfer
        result = transfer(args.rcx, args.send, args.transport)
    elif args.command == "shell":
        from mod_shell import connect
        result = connect(args.host, args.password_file, args.shell_command)
        if result is None:
            return
    else:
        result = tcp_services(args.host)
    print(json.dumps(result, indent=2))
    if args.command == "build" and result["returncode"]:
        raise SystemExit(result["returncode"])


if __name__ == "__main__":
    main()
