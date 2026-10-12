# Local USB update route in the recovery package

Static decompilation of the locally extracted `EPFWUPD.exe` shows a local update path separate from its HTTP `/DOWN/FIRMWAREUPDATE/ROM1` path. This is **not** execution of Epson's updater and did not contact the printer.

- `0x0044470f` opens `EPSON-CTRL`, sends five-byte `fl 01 00 01`, reads a reply, and in another branch sends `gm 01 00 01`. The binary logs these as `FL` and `GM`; the actual bytes are lowercase ASCII. It compares a reply with `OK` before advancing its state.
- `0x00444b6a` opens `EPSON-DATA` after acquiring a USB mutex.
- `0x00444bd1` obtains a write-unit size, reads source firmware data, and sends it in bounded chunks through the local transport's write method. The logs mention `Data(Z_%d)` and `D4Write`.
- `0x00444a42` sends a firmware-update end command through `EPSON-CTRL` and reads its reply.

The Windows package's generic `CENUSBHost` class opens a device interface, finds one bulk IN and one bulk OUT pipe, and delegates transfers to `WinUsb_ReadPipe`/`WinUsb_WritePipe`. The attached ET-3850 has such a WinUSB interface at `MI_02`, with OUT `0x08` and IN `0x89`. These facts narrow the USB transport, but the class also serves scanner-related objects. The mapping between the updater's `EPSON-CTRL`/`EPSON-DATA` names and the observed endpoints, the full packet framing, recovery-mode product ID, status replies, and firmware acceptance rules remain unverified.

No USB bulk packet, update command, firmware image, or print job has been sent in this investigation. The [USB connection note](usb-connection-and-recovery.md) records the live descriptors. The route is a basis for a self-built client and recovery study, not yet an install method.
