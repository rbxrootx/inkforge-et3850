"""Self-built USB firmware transfer for the owner's ET-3850.

The device-side custom-image acceptance and recovery behavior are unverified.
Preflight defaults to no transmission. Actual transfer requires ``--send``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from et3850 import SOURCE_SHA256, inspect_firmware, printer_queues
from usb_d4 import D4, UsbPipe, WinUsbPipe

CUSTOM_SHA256 = "99bae21d9ac8bbba31271dc962414ac4262e9c097d91a58b8033f5747d788249"
PHOTO_SHA256 = "b3dfbc88b93eda08dabe5e47045e5579ceda134ff3fac4df357a2979fb579972"
HEADER_BYTES = 0x112
DATA_PAYLOAD_BYTES = 32762  # observed DATA MTU 32768 minus the six-byte D4 header


def preflight(path: Path) -> tuple[dict, bytes]:
    path = path.resolve()
    data = path.read_bytes()
    report = inspect_firmware(path)
    digest = report["sha256"]
    if digest not in (SOURCE_SHA256, CUSTOM_SHA256, PHOTO_SHA256):
        raise ValueError("RCX is not a pinned XB22Q5 source or checked Wi-Fi/Telnet candidate")
    if data[HEADER_BYTES:HEADER_BYTES + 14] != b"EPSONSIGNXB20d":
        raise ValueError("unexpected RCX binary envelope")
    text = data[:HEADER_BYTES].decode("ascii")
    if not text.endswith("\f"):
        raise ValueError("RCX text header does not end at the expected form feed")
    sizes = [int(value) for value in re.findall(r'(?m)^5="(\d+)"\r?$', text)]
    if sizes != [len(data) - HEADER_BYTES]:
        raise ValueError(f"Z_1 size does not match binary payload: {sizes}")
    if len(report["records"]) != 3 or any(
        not all(record[key] for key in ("first_sum_ok", "second_sum_ok", "sha1_ok"))
        for record in report["records"]
    ):
        raise ValueError("record integrity check failed")
    block = report["signature_block"]
    if block["declared_payload"] != block["actual_payload"]:
        raise ValueError("declared and actual payload sizes differ")
    if digest == SOURCE_SHA256:
        if report["trailing_bytes_after_records"] != 0 or report["embedded_signature"] != "valid for embedded key only":
            raise ValueError("pinned source image failed original-layout checks")
    else:
        if report["trailing_bytes_after_records"] != 1 or report["embedded_signature"] != "invalid for embedded key":
            raise ValueError("custom candidate failed expected length-gate layout checks")
    kind = "stock" if digest == SOURCE_SHA256 else ("custom-photo" if digest == PHOTO_SHA256 else "custom")
    return {"image": str(path), "sha256": digest, "kind": kind,
            "rcx_bytes": len(data), "transfer_bytes": len(data) - HEADER_BYTES,
            "records_verified": 3, "signature": report["embedded_signature"],
            "device_acceptance": "unverified"}, data[HEADER_BYTES:]


def reply_text(reply: bytes, prefix: bytes) -> str:
    if not reply.startswith(prefix) or not reply.endswith(b";\x0c"):
        raise IOError(f"unexpected Epson control reply: {reply[:160]!r}")
    return reply.decode("ascii", "replace")


def transfer(path: Path, send: bool = False, transport: str = "usbprint") -> dict:
    report, blob = preflight(path)
    if not send:
        return report | {"action": "preflight only; no printer contact"}
    for queue in printer_queues():
        if queue.get("jobs", 0):
            raise RuntimeError("ET-3850 print queue has pending jobs; wait for it to become idle")
    if transport not in ("winusb", "usbprint"):
        raise ValueError("transport must be winusb or usbprint")
    print(f"Opening live ET-3850 D4 control channel via {transport}", flush=True)
    with D4(WinUsbPipe() if transport == "winusb" else UsbPipe()) as d4:
        sid = d4.open("EPSON-CTRL")
        version = reply_text(d4.call(sid, b"vi", b"\x04"), b"vi:04:")
        print(f"Device replied {version.strip()}", flush=True)
        if "XB22Q5" not in version:
            raise IOError("device firmware is not the pinned XB22Q5 build")
        if report["kind"] != "stock":
            print("Custom-image signature is invalid under normal verification; the isolated length-gate bypass is unproven on this device", flush=True)
        fl = reply_text(d4.call(sid, b"fl", b"\x01"), b"fl:")
        print(f"FL: {fl.strip()}", flush=True)
        gm = reply_text(d4.call(sid, b"gm", b"\x01"), b"fl:01:")
        print(f"GM: {gm.strip()}", flush=True)
        if gm != "fl:01:OK;\x0c":
            raise IOError("printer did not grant firmware download mode")
        d4.close_channel(sid)

        data_sid = d4.open("EPSON-DATA")
        total = len(blob)
        sent = 0
        next_report = 1024 * 1024
        start = time.monotonic()
        print(f"Streaming {total} RCX binary bytes in bounded D4 frames", flush=True)
        view = memoryview(blob)
        while sent < total:
            end = min(sent + DATA_PAYLOAD_BYTES, total)
            try:
                d4.send(data_sid, view[sent:end].tobytes(), eom=end == total)
            except Exception:
                print(f"DATA stopped after {sent}/{total} bytes", flush=True)
                raise
            sent = end
            if sent >= next_report or sent == total:
                print(f"DATA {sent}/{total} ({sent * 100 // total}%)", flush=True)
                next_report += 1024 * 1024
        d4.close_channel(data_sid)
        print(f"Data transport finished in {time.monotonic() - start:.1f}s; requesting update-end status", flush=True)
        d4.pipe.read_timeout_seconds = 180
        sid = d4.open("EPSON-CTRL")
        finish = reply_text(d4.call(sid, b"gm", b"\x03"), b"fl:03:")
        print(f"GM end: {finish.strip()}", flush=True)
        if finish != "fl:03:OK;\x0c":
            raise IOError("printer did not acknowledge firmware update end")
        d4.close_channel(sid)
    return report | {"action": "firmware transfer acknowledged; reboot and post-install validation pending",
                     "device_before": version.strip(), "device_end": finish.strip(), "sent_bytes": sent}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rcx", type=Path)
    parser.add_argument("--send", action="store_true", help="enter update mode and transmit image to the attached printer")
    parser.add_argument("--transport", choices=("winusb", "usbprint"), default="usbprint")
    args = parser.parse_args()
    print(json.dumps(transfer(args.rcx, args.send, args.transport), indent=2), flush=True)


if __name__ == "__main__":
    main()
