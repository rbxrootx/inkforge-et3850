"""ET-3850 USBPRINT IEEE 1284.4 transport, based on live MI_01 observations.

This module does not select update mode on import. Callers own command policy.
"""

from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import struct
import sys
import time
import winreg

DEVICE_ID = "VID_04B8&PID_1181&MI_01"
PRINTER_CLASS = r"SYSTEM\CurrentControlSet\Control\DeviceClasses\{28d78fad-5a12-11d1-ae5b-0000f803a8c2}"
ENTER_D4 = b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL\n@EJL\n"
LEAVE_D4 = b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL     \n"
FILE_FLAG_OVERLAPPED = 0x40000000
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258


class Overlapped(C.Structure):
    _fields_ = [("Internal", C.c_size_t), ("InternalHigh", C.c_size_t),
                ("Offset", W.DWORD), ("OffsetHigh", W.DWORD), ("hEvent", W.HANDLE)]


def usbprint_path() -> str:
    if sys.platform != "win32":
        raise RuntimeError("USBPRINT transport requires Windows")
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PRINTER_CLASS) as group:
        for index in range(winreg.QueryInfoKey(group)[0]):
            name = winreg.EnumKey(group, index)
            if DEVICE_ID in name.upper():
                return "\\\\?\\" + name[4:]
    raise RuntimeError("attached ET-3850 USBPRINT MI_01 path not found")


class UsbPipe:
    def __init__(self):
        kernel = C.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID,
                                       W.DWORD, W.DWORD, W.HANDLE]
        kernel.CreateFileW.restype = W.HANDLE
        kernel.ReadFile.argtypes = [W.HANDLE, W.LPVOID, W.DWORD, C.POINTER(W.DWORD), C.POINTER(Overlapped)]
        kernel.ReadFile.restype = W.BOOL
        kernel.WriteFile.argtypes = [W.HANDLE, W.LPCVOID, W.DWORD, C.POINTER(W.DWORD), C.POINTER(Overlapped)]
        kernel.WriteFile.restype = W.BOOL
        kernel.CloseHandle.argtypes = [W.HANDLE]
        kernel.CreateEventW.argtypes = [W.LPVOID, W.BOOL, W.BOOL, W.LPCWSTR]
        kernel.CreateEventW.restype = W.HANDLE
        kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        kernel.WaitForSingleObject.restype = W.DWORD
        kernel.GetOverlappedResult.argtypes = [W.HANDLE, C.POINTER(Overlapped), C.POINTER(W.DWORD), W.BOOL]
        kernel.GetOverlappedResult.restype = W.BOOL
        kernel.CancelIoEx.argtypes = [W.HANDLE, C.POINTER(Overlapped)]
        kernel.CancelIoEx.restype = W.BOOL
        self.kernel = kernel
        self.handle = kernel.CreateFileW(usbprint_path(), 0xC0000000, 3, None, 3, FILE_FLAG_OVERLAPPED, None)
        if self.handle == W.HANDLE(-1).value:
            raise OSError(C.get_last_error(), "opening ET-3850 USBPRINT interface")
        self.pending = bytearray()
        self.read_timeout_seconds = 5

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def _io(self, is_write: bool, buffer, size: int, timeout_ms: int):
        event = self.kernel.CreateEventW(None, True, False, None)
        if not event:
            raise OSError(C.get_last_error(), "creating USB I/O event")
        ov = Overlapped()
        ov.hEvent = event
        count = W.DWORD()
        try:
            function = self.kernel.WriteFile if is_write else self.kernel.ReadFile
            ok = function(self.handle, buffer, size, C.byref(count), C.byref(ov))
            if not ok:
                error = C.get_last_error()
                if error != ERROR_IO_PENDING:
                    raise OSError(error, "USBPRINT write" if is_write else "USBPRINT read")
                waited = self.kernel.WaitForSingleObject(event, timeout_ms)
                if waited == WAIT_TIMEOUT:
                    self.kernel.CancelIoEx(self.handle, C.byref(ov))
                    self.kernel.WaitForSingleObject(event, 1000)
                    raise TimeoutError("USBPRINT write timed out" if is_write else "USBPRINT read timed out")
                if waited != WAIT_OBJECT_0:
                    raise OSError(C.get_last_error(), "waiting for USBPRINT I/O")
                if not self.kernel.GetOverlappedResult(self.handle, C.byref(ov), C.byref(count), False):
                    raise OSError(C.get_last_error(), "completing USBPRINT I/O")
            return count.value
        finally:
            self.kernel.CloseHandle(event)

    def write(self, data: bytes, timeout_ms: int = 10000):
        buffer = C.create_string_buffer(data)
        count = self._io(True, buffer, len(data), timeout_ms)
        if count != len(data):
            raise IOError(f"short USB write: {count}/{len(data)}")

    def read_raw(self, timeout_ms: int = 5000) -> bytes:
        buffer = C.create_string_buffer(65536)
        try:
            count = self._io(False, buffer, len(buffer), timeout_ms)
        except TimeoutError:
            return b""
        return buffer.raw[:count]

    def drain(self):
        self.pending.clear()
        for _ in range(4):
            if not self.read_raw(150):
                break

    def read(self, size: int) -> bytes:
        deadline = time.monotonic() + self.read_timeout_seconds
        while len(self.pending) < size:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                raise TimeoutError(f"USBPRINT read: {len(self.pending)}/{size} bytes")
            chunk = self.read_raw(remaining_ms)
            if chunk:
                self.pending.extend(chunk)
        value = bytes(self.pending[:size])
        del self.pending[:size]
        return value

    def frame(self, psid: int, ssid: int, credit: int, control: int, payload: bytes):
        length = len(payload) + 6
        if length > 65535:
            raise ValueError("D4 frame exceeds 16-bit length")
        self.write(struct.pack(">BBHBB", psid, ssid, length, credit, control) + payload)

    def read_frame(self):
        psid, ssid, length, credit, control = struct.unpack(">BBHBB", self.read(6))
        if length < 6:
            raise IOError(f"invalid D4 frame length {length}")
        return psid, ssid, credit, control, self.read(length - 6)


def winusb_paths() -> list[str]:
    base = r"SYSTEM\CurrentControlSet\Control\DeviceClasses"
    paths = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as classes:
        for index in range(winreg.QueryInfoKey(classes)[0]):
            guid = winreg.EnumKey(classes, index)
            with winreg.OpenKey(classes, guid) as group:
                for item in range(winreg.QueryInfoKey(group)[0]):
                    name = winreg.EnumKey(group, item)
                    if "VID_04B8&PID_1181&MI_02" in name.upper():
                        paths.append("\\\\?\\" + name[4:])
    return paths


class WinUsbPipe(UsbPipe):
    """CENUSBHost-style D4 transport through the ET-3850 WinUSB MI_02 pipes."""

    def __init__(self):
        kernel = C.WinDLL("kernel32", use_last_error=True)
        usb = C.WinDLL("winusb", use_last_error=True)
        kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID,
                                       W.DWORD, W.DWORD, W.HANDLE]
        kernel.CreateFileW.restype = W.HANDLE
        kernel.CloseHandle.argtypes = [W.HANDLE]
        kernel.CreateEventW.argtypes = [W.LPVOID, W.BOOL, W.BOOL, W.LPCWSTR]
        kernel.CreateEventW.restype = W.HANDLE
        kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        kernel.WaitForSingleObject.restype = W.DWORD
        kernel.GetOverlappedResult.argtypes = [W.HANDLE, C.POINTER(Overlapped), C.POINTER(W.DWORD), W.BOOL]
        kernel.GetOverlappedResult.restype = W.BOOL
        kernel.CancelIoEx.argtypes = [W.HANDLE, C.POINTER(Overlapped)]
        kernel.CancelIoEx.restype = W.BOOL
        usb.WinUsb_Initialize.argtypes = [W.HANDLE, C.POINTER(W.HANDLE)]
        usb.WinUsb_Initialize.restype = W.BOOL
        usb.WinUsb_Free.argtypes = [W.HANDLE]
        usb.WinUsb_ReadPipe.argtypes = [W.HANDLE, C.c_ubyte, W.LPVOID, W.DWORD,
                                        C.POINTER(W.DWORD), C.POINTER(Overlapped)]
        usb.WinUsb_ReadPipe.restype = W.BOOL
        usb.WinUsb_WritePipe.argtypes = [W.HANDLE, C.c_ubyte, W.LPVOID, W.DWORD,
                                         C.POINTER(W.DWORD), C.POINTER(Overlapped)]
        usb.WinUsb_WritePipe.restype = W.BOOL
        self.kernel, self.usb = kernel, usb
        self.handle = None
        self.win_handle = W.HANDLE()
        self.pending = bytearray()
        self.read_timeout_seconds = 5
        last_error = 2
        for path in winusb_paths():
            handle = kernel.CreateFileW(path, 0xC0000000, 3, None, 3, FILE_FLAG_OVERLAPPED, None)
            if handle == W.HANDLE(-1).value:
                last_error = C.get_last_error()
                continue
            if usb.WinUsb_Initialize(handle, C.byref(self.win_handle)):
                self.handle = handle
                self.path = path
                break
            last_error = C.get_last_error()
            kernel.CloseHandle(handle)
        if self.handle is None:
            raise OSError(last_error, "opening ET-3850 WinUSB MI_02")

    def close(self):
        if self.handle is not None:
            self.usb.WinUsb_Free(self.win_handle)
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def _io(self, is_write: bool, buffer, size: int, timeout_ms: int):
        event = self.kernel.CreateEventW(None, True, False, None)
        if not event:
            raise OSError(C.get_last_error(), "creating WinUSB event")
        ov = Overlapped()
        ov.hEvent = event
        count = W.DWORD()
        pipe_id = 0x08 if is_write else 0x89
        try:
            function = self.usb.WinUsb_WritePipe if is_write else self.usb.WinUsb_ReadPipe
            ok = function(self.win_handle, pipe_id, buffer, size, C.byref(count), C.byref(ov))
            if not ok:
                error = C.get_last_error()
                if error != ERROR_IO_PENDING:
                    raise OSError(error, "WinUSB write" if is_write else "WinUSB read")
                waited = self.kernel.WaitForSingleObject(event, timeout_ms)
                if waited == WAIT_TIMEOUT:
                    self.kernel.CancelIoEx(self.handle, C.byref(ov))
                    self.kernel.WaitForSingleObject(event, 1000)
                    raise TimeoutError("WinUSB write timed out" if is_write else "WinUSB read timed out")
                if waited != WAIT_OBJECT_0:
                    raise OSError(C.get_last_error(), "waiting for WinUSB I/O")
                if not self.kernel.GetOverlappedResult(self.handle, C.byref(ov), C.byref(count), False):
                    raise OSError(C.get_last_error(), "completing WinUSB I/O")
            return count.value
        finally:
            self.kernel.CloseHandle(event)


class D4:
    def __init__(self, pipe=None):
        self.pipe = pipe if pipe is not None else UsbPipe()
        self.initialized = False
        self.control_credit = 1
        self.channels: dict[int, dict] = {}
        try:
            self.pipe.drain()
            self.pipe.write(ENTER_D4)
            # A previous BDC response can remain queued after a client exits.
            # The D4 negotiation reply has an eight-byte, fixed framing marker.
            marker = b"\x00\x00\x00\x08\x01\x00"
            window = bytearray()
            for _ in range(262144):
                window.extend(self.pipe.read(1))
                if len(window) > len(marker):
                    del window[0]
                if bytes(window) == marker:
                    break
            else:
                raise IOError("D4 negotiation reply not found")
            self.pipe.read(2)
            init_reply = self.command(0, b"\x10")
            if init_reply not in (b"\x10", b"\x00"):
                raise IOError(f"D4 Init response mismatch: {init_reply.hex()}")
            self.initialized = True
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.pipe.handle is not None:
            try:
                if self.initialized:
                    for sid in tuple(self.channels):
                        try:
                            self.close_channel(sid)
                        except OSError:
                            pass
                    self.pipe.frame(0, 0, 1, 0, b"\x08")
            except OSError:
                pass
            self.pipe.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def command(self, number: int, payload: bytes = b"") -> bytes:
        if number and self.control_credit < 1:
            raise IOError("control channel has no transmit credit")
        self.pipe.frame(0, 0, 1, 0, bytes([number]) + payload)
        if number:
            self.control_credit -= 1
        while True:
            psid, ssid, credit, control, reply = self.pipe.read_frame()
            if psid != 0 or ssid != 0:
                channel = self.channels.get(psid)
                if channel is None or ssid != psid:
                    raise IOError(f"unexpected channel frame during control command: {psid}/{ssid}")
                channel["tx_credit"] += credit
                channel["rx_queue"].append((control, reply))
                continue
            self.control_credit += credit
            if not reply:
                continue
            if reply[0] == 0x7f:
                raise IOError(f"D4 control error {reply.hex()}")
            if len(reply) < 2 or reply[0] != (number | 0x80) or reply[1] != 0:
                raise IOError(f"D4 command {number:#x} rejected: {reply.hex()}")
            return reply[2:]

    def open(self, name: str) -> int:
        sid_reply = self.command(9, name.encode("ascii"))
        if not sid_reply or sid_reply[1:] != name.encode("ascii"):
            raise IOError(f"invalid socket ID response: {sid_reply.hex()}")
        sid = sid_reply[0]
        # The local Epson updater and independent D4 client request all four
        # 16-bit credit/MTU fields at 0xffff. Zero receive-credit fields worked
        # for short status replies but did not sustain firmware data streaming.
        reply = self.command(1, struct.pack(">BBHHHH", sid, sid, 0xffff, 0xffff, 0xffff, 0xffff))
        if len(reply) < 8:
            raise IOError(f"short channel open response: {reply.hex()}")
        psid, ssid, mtu, max_credit, credit = struct.unpack(">BBHHH", reply[:8])
        if psid != sid or ssid != sid or mtu < 7:
            raise IOError(f"invalid channel parameters: {reply.hex()}")
        self.channels[sid] = {"mtu": mtu, "max_credit": max_credit,
                              "tx_credit": credit, "rx_queue": []}
        return sid

    def close_channel(self, sid: int):
        self.command(2, struct.pack(">BB", sid, sid))
        self.channels.pop(sid, None)

    def grant_rx(self, sid: int, amount: int = 1):
        self.command(3, struct.pack(">BBH", sid, sid, amount))

    def ensure_tx_credit(self, sid: int):
        channel = self.channels[sid]
        deadline = time.monotonic() + (600 if sid == 64 else 10)
        next_notice = time.monotonic() + 15
        while time.monotonic() < deadline:
            if channel["tx_credit"]:
                return
            # XB22Q5 updater constant at 0x66c49c uses revision-0x10
            # CreditRequest: socket pair, 0xfffe, 0xffff (six payload bytes).
            reply = self.command(4, struct.pack(">BBHH", sid, sid, 0xfffe, 0xffff))
            if len(reply) < 4 or reply[:2] != bytes([sid, sid]):
                raise IOError(f"invalid credit response: {reply.hex()}")
            channel["tx_credit"] += struct.unpack(">H", reply[2:4])[0]
            if not channel["tx_credit"]:
                if time.monotonic() >= next_notice:
                    print(f"D4 channel {sid}: waiting for printer transmit credit", flush=True)
                    next_notice = time.monotonic() + 15
                time.sleep(0.25)
        raise TimeoutError(f"no transmit credit for D4 channel {sid}")

    def send(self, sid: int, payload: bytes, eom: bool = True):
        channel = self.channels[sid]
        mtu = min(channel["mtu"], 32768)
        if not payload:
            raise ValueError("empty D4 payload")
        for offset in range(0, len(payload), mtu - 6):
            chunk = payload[offset:offset + mtu - 6]
            self.ensure_tx_credit(sid)
            final = eom and offset + len(chunk) == len(payload)
            self.pipe.frame(sid, sid, 0, 2 if final else 0, chunk)
            channel["tx_credit"] -= 1

    def receive(self, sid: int) -> bytes:
        queued = self.channels[sid]["rx_queue"]
        if queued:
            return queued.pop(0)[1]
        # Epson's BDC replies on this device are single OOB frames (control=1).
        # Waiting for EOM here hangs because the printer does not set that bit.
        psid, ssid, credit, control, payload = self.pipe.read_frame()
        if psid != sid or ssid != sid:
            raise IOError(f"unexpected D4 channel: {psid}/{ssid}")
        self.channels[sid]["tx_credit"] += credit
        return payload

    def call(self, sid: int, name: bytes, argument: bytes) -> bytes:
        if len(name) != 2:
            raise ValueError("two-byte BDC command required")
        self.send(sid, name + struct.pack("<H", len(argument)) + argument)
        self.grant_rx(sid)
        return self.receive(sid)


def read_identity(winusb: bool = False) -> dict:
    with D4(WinUsbPipe() if winusb else UsbPipe()) as d4:
        sid = d4.open("EPSON-CTRL")
        try:
            version = d4.call(sid, b"vi", b"\x04")
            status = d4.call(sid, b"st", b"\x01")
            return {"interface": "WinUSB MI_02" if winusb else "USBPRINT MI_01", "version_reply": version.decode("ascii", "replace"),
                    "status_reply_prefix": status[:16].hex(), "status_reply_bytes": len(status)}
        finally:
            d4.close_channel(sid)


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--winusb", action="store_true", help="query the MI_02 WinUSB D4 interface")
    args = parser.parse_args()
    print(json.dumps(read_identity(args.winusb), indent=2))
