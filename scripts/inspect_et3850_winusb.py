"""Read-only descriptor enumeration of the attached ET-3850 WinUSB interfaces."""
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
usb = C.WinDLL("winusb", use_last_error=True)
kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID,
                               W.DWORD, W.DWORD, W.HANDLE]
kernel.CreateFileW.restype = W.HANDLE
kernel.CloseHandle.argtypes = [W.HANDLE]
usb.WinUsb_Initialize.argtypes = [W.HANDLE, C.POINTER(W.HANDLE)]
usb.WinUsb_Initialize.restype = W.BOOL
usb.WinUsb_Free.argtypes = [W.HANDLE]
usb.WinUsb_QueryInterfaceSettings.argtypes = [W.HANDLE, C.c_ubyte,
                                               C.POINTER(InterfaceDescriptor)]
usb.WinUsb_QueryInterfaceSettings.restype = W.BOOL
usb.WinUsb_QueryPipe.argtypes = [W.HANDLE, C.c_ubyte, C.c_ubyte,
                                 C.POINTER(PipeInfo)]
usb.WinUsb_QueryPipe.restype = W.BOOL
usb.WinUsb_GetAssociatedInterface.argtypes = [W.HANDLE, C.c_ubyte,
                                               C.POINTER(W.HANDLE)]
usb.WinUsb_GetAssociatedInterface.restype = W.BOOL


def show_interface(handle, label):
    desc = InterfaceDescriptor()
    if not usb.WinUsb_QueryInterfaceSettings(handle, 0, C.byref(desc)):
        print(label, "QueryInterfaceSettings error", C.get_last_error())
        return
    print(label, "interface", desc.number, "alternate", desc.alternate,
          "class", f"{desc.device_class:02x}:{desc.subclass:02x}:{desc.protocol:02x}",
          "endpoints", desc.endpoints)
    for index in range(desc.endpoints):
        pipe = PipeInfo()
        if usb.WinUsb_QueryPipe(handle, 0, index, C.byref(pipe)):
            print("  pipe", index, "type", pipe.pipe_type,
                  "id", f"0x{pipe.pipe_id:02x}", "max_packet", pipe.max_packet,
                  "interval", pipe.interval)
        else:
            print("  pipe", index, "error", C.get_last_error())


base = r"SYSTEM\CurrentControlSet\Control\DeviceClasses"
with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as classes:
    for n in range(winreg.QueryInfoKey(classes)[0]):
        guid = winreg.EnumKey(classes, n)
        with winreg.OpenKey(classes, guid) as class_key:
            for m in range(winreg.QueryInfoKey(class_key)[0]):
                key = winreg.EnumKey(class_key, m)
                if "VID_04B8&PID_1181&MI_02" not in key.upper():
                    continue
                # Registry names are ##?#USB#VID...#instance#{guid}; device paths
                # retain # separators after the leading \\?\ marker.
                path = "\\\\?\\" + key[4:]
                print("PATH", path)
                fd = kernel.CreateFileW(path, 0xC0000000, 3, None, 3, 0x40000000, None)
                if fd == W.HANDLE(-1).value:
                    print("CreateFile error", C.get_last_error())
                    continue
                try:
                    primary = W.HANDLE()
                    if not usb.WinUsb_Initialize(fd, C.byref(primary)):
                        print("WinUsb_Initialize error", C.get_last_error())
                        continue
                    try:
                        show_interface(primary, "primary")
                        for index in range(4):
                            associated = W.HANDLE()
                            if not usb.WinUsb_GetAssociatedInterface(primary, index,
                                                                       C.byref(associated)):
                                print("associated", index, "error", C.get_last_error())
                                break
                            try:
                                show_interface(associated, f"associated {index}")
                            finally:
                                usb.WinUsb_Free(associated)
                    finally:
                        usb.WinUsb_Free(primary)
                finally:
                    kernel.CloseHandle(fd)
