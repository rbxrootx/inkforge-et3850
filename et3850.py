#!/usr/bin/env python3
"""ET-3850 jailbreak workbench. Local analysis and explicit offline patch builds.

The USB firmware framing and device acceptance checks are still under research.
This client never transmits firmware. It deliberately has no fake "install" path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
ASSETS = ROOT / "assets"
SOURCE_SHA256 = "103c9514e57f143f2619abcd280bd4d0926abf5370e03d28753a334ae02cd675"
VID_PID = "VID_04B8&PID_1181"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def usb_devices() -> list[dict]:
    """Enumerate the exact ET-3850 PnP ID; no USB packets are sent."""
    if sys.platform != "win32":
        return []
    import winreg

    result = []
    base = r"SYSTEM\CurrentControlSet\Enum\USB"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
            names = [winreg.EnumKey(root, i) for i in range(winreg.QueryInfoKey(root)[0])]
        for name in names:
            if VID_PID not in name.upper():
                continue
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + "\\" + name) as product:
                instances = [winreg.EnumKey(product, i) for i in range(winreg.QueryInfoKey(product)[0])]
            for instance in instances:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + "\\" + name + "\\" + instance) as key:
                    values = {}
                    for field in ("FriendlyName", "DeviceDesc", "Service", "ClassGUID"):
                        try:
                            values[field] = winreg.QueryValueEx(key, field)[0]
                        except FileNotFoundError:
                            pass
                    result.append({"device_id": name, "instance": instance, **values})
    except OSError as error:
        return [{"error": str(error)}]
    return result


def usb_bulk_interface() -> list[dict]:
    """Query attached MI_02 pipe descriptors with WinUSB; performs no pipe I/O."""
    if sys.platform != "win32":
        return []
    import ctypes as C
    from ctypes import wintypes as W
    import winreg

    class InterfaceDescriptor(C.Structure):
        _fields_ = [(name, C.c_ubyte) for name in (
            "length", "descriptor_type", "number", "alternate", "endpoints",
            "device_class", "subclass", "protocol", "string_index")]

    class PipeInfo(C.Structure):
        _fields_ = [("pipe_type", C.c_int), ("pipe_id", C.c_ubyte),
                    ("max_packet", C.c_ushort), ("interval", C.c_ubyte)]

    kernel = C.WinDLL("kernel32", use_last_error=True)
    winusb = C.WinDLL("winusb", use_last_error=True)
    kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID,
                                   W.DWORD, W.DWORD, W.HANDLE]
    kernel.CreateFileW.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    winusb.WinUsb_Initialize.argtypes = [W.HANDLE, C.POINTER(W.HANDLE)]
    winusb.WinUsb_Initialize.restype = W.BOOL
    winusb.WinUsb_QueryInterfaceSettings.argtypes = [W.HANDLE, C.c_ubyte,
                                                    C.POINTER(InterfaceDescriptor)]
    winusb.WinUsb_QueryInterfaceSettings.restype = W.BOOL
    winusb.WinUsb_QueryPipe.argtypes = [W.HANDLE, C.c_ubyte, C.c_ubyte,
                                       C.POINTER(PipeInfo)]
    winusb.WinUsb_QueryPipe.restype = W.BOOL
    winusb.WinUsb_Free.argtypes = [W.HANDLE]
    paths = []
    base = r"SYSTEM\CurrentControlSet\Control\DeviceClasses"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as classes:
        for i in range(winreg.QueryInfoKey(classes)[0]):
            guid = winreg.EnumKey(classes, i)
            with winreg.OpenKey(classes, guid) as group:
                for j in range(winreg.QueryInfoKey(group)[0]):
                    key = winreg.EnumKey(group, j)
                    if "VID_04B8&PID_1181&MI_02" in key.upper():
                        paths.append("\\\\?\\" + key[4:])
    reports = []
    for path in paths:
        report = {"path": path, "pipes": []}
        fd = kernel.CreateFileW(path, 0xC0000000, 3, None, 3, 0x40000000, None)
        if fd == W.HANDLE(-1).value:
            report["error"] = f"CreateFileW: {C.get_last_error()}"
            reports.append(report)
            continue
        try:
            handle = W.HANDLE()
            if not winusb.WinUsb_Initialize(fd, C.byref(handle)):
                report["error"] = f"WinUsb_Initialize: {C.get_last_error()}"
            else:
                try:
                    desc = InterfaceDescriptor()
                    if winusb.WinUsb_QueryInterfaceSettings(handle, 0, C.byref(desc)):
                        report["interface"] = desc.number
                        report["class_triplet"] = f"{desc.device_class:02x}:{desc.subclass:02x}:{desc.protocol:02x}"
                        for k in range(desc.endpoints):
                            pipe = PipeInfo()
                            if winusb.WinUsb_QueryPipe(handle, 0, k, C.byref(pipe)):
                                report["pipes"].append({"type": "bulk" if pipe.pipe_type == 2 else pipe.pipe_type,
                                                        "endpoint": f"0x{pipe.pipe_id:02x}",
                                                        "max_packet": pipe.max_packet})
                    else:
                        report["error"] = f"WinUsb_QueryInterfaceSettings: {C.get_last_error()}"
                finally:
                    winusb.WinUsb_Free(handle)
        finally:
            kernel.CloseHandle(fd)
        reports.append(report)
    return reports


def printer_queues() -> list[dict]:
    """Read Windows spooler queue metadata, without submitting a job."""
    if sys.platform != "win32":
        return []
    import ctypes as C
    from ctypes import wintypes as W

    class PRINTER_INFO_2W(C.Structure):
        _fields_ = [(name, W.LPWSTR) for name in (
            "pServerName", "pPrinterName", "pShareName", "pPortName", "pDriverName",
            "pComment", "pLocation")]
        _fields_ += [("pDevMode", W.LPVOID), ("pSepFile", W.LPWSTR),
                     ("pPrintProcessor", W.LPWSTR), ("pDatatype", W.LPWSTR),
                     ("pParameters", W.LPWSTR), ("pSecurityDescriptor", W.LPVOID),
                     ("Attributes", W.DWORD), ("Priority", W.DWORD),
                     ("DefaultPriority", W.DWORD), ("StartTime", W.DWORD),
                     ("UntilTime", W.DWORD), ("Status", W.DWORD), ("cJobs", W.DWORD),
                     ("AveragePPM", W.DWORD)]

    spool = C.WinDLL("winspool.drv", use_last_error=True)
    spool.EnumPrintersW.argtypes = [W.DWORD, W.LPWSTR, W.DWORD, W.LPBYTE,
                                   W.DWORD, C.POINTER(W.DWORD), C.POINTER(W.DWORD)]
    needed, count = W.DWORD(), W.DWORD()
    spool.EnumPrintersW(2 | 4, None, 2, None, 0, C.byref(needed), C.byref(count))
    if not needed.value:
        return []
    buffer = C.create_string_buffer(needed.value)
    ok = spool.EnumPrintersW(2 | 4, None, 2, C.cast(buffer, W.LPBYTE), needed.value,
                             C.byref(needed), C.byref(count))
    if not ok:
        return [{"error": f"EnumPrintersW: {C.get_last_error()}"}]
    entries = C.cast(buffer, C.POINTER(PRINTER_INFO_2W))
    return [{"name": entries[i].pPrinterName, "port": entries[i].pPortName,
             "driver": entries[i].pDriverName, "status": entries[i].Status,
             "jobs": entries[i].cJobs} for i in range(count.value)
            if "ET-3850" in (entries[i].pPrinterName or "").upper()]


def inspect_firmware(path: Path) -> dict:
    """Check the signed container layout and record integrity without loading a device."""
    path = path.resolve()
    data = path.read_bytes()
    marker = b"EPSONSIGNXB20d"
    offset = data.find(marker)
    report = {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
              "is_pinned_source": False, "signature_block": None, "records": [],
              "embedded_signature": "not checked", "device_trust": "not established"}
    report["is_pinned_source"] = report["sha256"] == SOURCE_SHA256
    if offset < 0 or offset + 4096 > len(data):
        report["error"] = "EPSONSIGNXB20d block absent or truncated"
        return report
    declared = struct.unpack_from("<I", data, offset + 16)[0]
    actual = len(data) - offset - 4096
    report["signature_block"] = {"offset": offset, "declared_payload": declared,
                                 "actual_payload": actual, "length_delta": declared - actual,
                                 "signature_present": any(data[offset + 32:offset + 96])}
    pos = offset + 4096
    for expected in range(3):
        if not data[pos:pos + 14].startswith(b"EPSON IPLJ6XB"):
            report["record_error"] = f"missing record {expected} at {pos:#x}"
            break
        first = struct.unpack_from("<I", data, pos + 0x1c)[0]
        second = struct.unpack_from("<I", data, pos + 0x40)[0]
        ident = struct.unpack_from("<H", data, pos + 0x38)[0]
        if first > len(data) or second > len(data) or pos + 4096 + first + second > len(data):
            report["record_error"] = f"invalid record {expected} lengths"
            break
        header = data[pos:pos + 4096]
        a = data[pos + 4096:pos + 4096 + first]
        b = data[pos + 4096 + first:pos + 4096 + first + second]
        report["records"].append({"id": ident, "offset": pos, "first_bytes": first,
                                  "second_bytes": second,
                                  "first_sum_ok": (sum(a) & 0xffff) == struct.unpack_from("<H", header, 0x12)[0],
                                  "second_sum_ok": (sum(b) & 0xffff) == struct.unpack_from("<H", header, 0x36)[0],
                                  "sha1_ok": hashlib.sha1(b + hashlib.sha1(header[:14]).digest()).digest() == header[0x44:0x58]})
        pos += 4096 + first + second
    report["trailing_bytes_after_records"] = len(data) - pos
    if declared == actual and len(data) >= 0xb122 + 64:
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec, utils
            sig = data[offset + 32:offset + 96]
            key_data = data[0xb122:0xb122 + 64]
            key = ec.EllipticCurvePublicNumbers(int.from_bytes(key_data[:32], "big"),
                                                int.from_bytes(key_data[32:], "big"),
                                                ec.SECP256R1()).public_key()
            digest = hashlib.sha256(data[offset + 4096:]).digest()
            key.verify(utils.encode_dss_signature(int.from_bytes(sig[:32], "big"),
                                                  int.from_bytes(sig[32:], "big")), digest,
                       ec.ECDSA(utils.Prehashed(hashes.SHA256())))
            report["embedded_signature"] = "valid for embedded key only"
        except ImportError:
            report["embedded_signature"] = "cryptography package unavailable"
        except (ValueError, InvalidSignature):
            report["embedded_signature"] = "invalid for embedded key"
    elif declared != actual:
        report["embedded_signature"] = "normal signature scope has length mismatch"
    return report


def build_candidate(original: Path, squashfs: Path, output: Path,
                    append_byte: bool = True, patch_ipl: bool = True,
                    first_squashfs: Path | None = None) -> dict:
    """Run our existing hash-locked offline builder as an isolated Python process."""
    original, squashfs, output = (p.resolve() for p in (original, squashfs, output))
    if original == output or squashfs == output:
        raise ValueError("output must be separate from input files")
    if ROOT in output.parents or output == ROOT:
        raise ValueError("firmware output must stay outside the public research repository")
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


def tcp_services(host: str, timeout: float = 1.5) -> dict:
    """Check only SSH and Telnet on an explicitly supplied printer address."""
    result = {}
    for name, port in (("ssh", 22), ("telnet", 23)):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                result[name] = "TCP open"
        except (OSError, TimeoutError) as error:
            result[name] = f"unavailable ({type(error).__name__})"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="launch the retro graphical workbench")
    sub.add_parser("status", help="read local USB and printer queue status")
    usb_status = sub.add_parser("usb-status", help="read live D4 version and status")
    usb_status.add_argument("--winusb", action="store_true", help="use MI_02 instead of USBPRINT MI_01")
    inspect = sub.add_parser("inspect", help="offline RCX integrity and signature report")
    inspect.add_argument("rcx", type=Path)
    build = sub.add_parser("build", help="build an offline length-gate candidate")
    build.add_argument("source_rcx", type=Path)
    build.add_argument("replacement_squashfs", type=Path)
    build.add_argument("output_rcx", type=Path)
    build.add_argument("--no-append-byte", action="store_true")
    build.add_argument("--no-ipl-patch", action="store_true")
    build.add_argument("--first-squashfs", type=Path)
    flash = sub.add_parser("flash", help="hash-locked RCX preflight; --send contacts the printer")
    flash.add_argument("rcx", type=Path)
    flash.add_argument("--send", action="store_true")
    flash.add_argument("--transport", choices=("usbprint", "winusb"), default="usbprint")
    probe = sub.add_parser("services", help="probe only TCP 22/23 on the supplied address")
    probe.add_argument("host")
    args = parser.parse_args()
    if args.command in (None, "gui"):
        from et3850_gui import run
        run()
        return
    if args.command == "status":
        result = {"usb": usb_devices(), "queues": printer_queues(),
                  "winusb": usb_bulk_interface(),
                  "update_transport": "partial signed-stock transfer only; no custom image sent"}
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
    else:
        result = tcp_services(args.host)
    print(json.dumps(result, indent=2))
    if args.command == "build" and result["returncode"]:
        raise SystemExit(result["returncode"])


if __name__ == "__main__":
    main()
