# Local USB update route in the recovery package

Static decompilation of the locally extracted `EPFWUPD.exe` shows a local update path separate from its HTTP `/DOWN/FIRMWAREUPDATE/ROM1` path. This is **not** execution of Epson's updater and did not contact the printer.

- `0x0044470f` opens `EPSON-CTRL`, sends five-byte `fl 01 00 01`, reads a reply, and in another branch sends `gm 01 00 01`. The binary logs these as `FL` and `GM`; the actual bytes are lowercase ASCII. It compares a reply with `OK` before advancing its state.
- `0x00444b6a` opens `EPSON-DATA` after acquiring a USB mutex.
- `0x00444bd1` obtains a write-unit size, reads source firmware data, and sends it in bounded chunks through the local transport's write method. The logs mention `Data(Z_%d)` and `D4Write`.
- `0x00444a42` sends a firmware-update end command through `EPSON-CTRL` and reads its reply.

The Windows package's generic `CENUSBHost` class opens a device interface, finds one bulk IN and one bulk OUT pipe, and delegates transfers to `WinUsb_ReadPipe`/`WinUsb_WritePipe`. The attached ET-3850 has such a WinUSB interface at `MI_02`, with OUT `0x08` and IN `0x89`. The class also serves scanner-related objects, so this alone does not identify the firmware data interface.

## Live ET-3850 USBPRINT result (2026-10-12)

The attached ET-3850's USBPRINT `MI_01` device interface accepts the EJL 1284.4 enter sequence. Our own Windows Python implementation in [`usb_d4.py`](../usb_d4.py) then completed D4 Init, opened `EPSON-CTRL` socket 2, read `vi:04:05.15.XB22Q5.FY20`, and received a 137-byte `@BDC ST2` status reply. It also opened `EPSON-DATA` socket 64, reporting a 32768-byte MTU and four data transmit credits after CreditRequest. Repeated read-only sessions work after timed input draining. The official updater binary was decompiled locally; it was not executed.

The separate WinUSB `MI_02` interface also completes EJL/D4 Init and returns the same `vi`/`st` replies. A signed-stock test there received `fl:;` and `fl:01:OK;\f`, but `EPSON-DATA` socket lookup returned D4 error `0x0a` before any image byte was sent. WinUSB alone is therefore not a working DATA route in this test. Both USB interfaces still returned the same firmware version and status afterward.

Further inspection of updater routine `0x0044470f` shows its successful FL/GM branch leaves `EPSON-CTRL` open. Routine `0x00444a42` reuses that control socket for the update-end command when the socket field is set. The earlier self-built sender closed CTRL before DATA; its next revision keeps CTRL open. The first live attempt with this corrected sequence returned `fl:01:BUSY` before opening DATA. The owner then reported the panel was displaying “Preparing for firmware update,” so the corrected sequence has not yet been evaluated through a DATA transfer.

The local updater's OpenChannel constant at `0x66c398` requests four `0xffff` fields. Its revision-0x10 CreditRequest constant at `0x66c49c` is a 13-byte D4 frame whose payload is command `04`, the socket pair, `fffe`, and `ffff`. These bytes now drive the self-built transport. The updater's local send routine derives a 32762-byte data unit from the observed MTU.

[`usb_update.py`](../usb_update.py) checks exact pinned SHA-256 hashes, the RCX size and three record checks, and the current device version before live transmission. It sends `fl(1)` and `gm(1)` over `EPSON-CTRL`; the printer replied `fl:;` and `fl:01:OK;\f`. It then opened `EPSON-DATA` and streamed the **unchanged, signed XB22Q5** binary payload. Several controlled attempts stopped before the full 40,607,744 bytes were sent:

| Data frame size and channel fields | Last completed byte count | Failure |
| --- | ---: | --- |
| 4090 payload, zero trailing OpenChannel fields | at least 23,071,690 | transmit credit/write failure |
| 32762 payload, zero trailing OpenChannel fields | 7,797,356 | USBPRINT write error 5 |
| 32762 payload, full OpenChannel fields | 18,772,626 | USBPRINT write error 5 |
| 32762 payload, full OpenChannel and six-byte CreditRequest | 1,801,910 | USBPRINT write error 5 |

The stop offset varies with transfer setup, so it has not established a firmware record boundary or signature rejection. The printer's USB interface temporarily disappeared and the owner observed a reboot. It subsequently returned to the main menu and again answered `XB22Q5` and `@BDC ST2`. No transfer reached `gm(3)` update-end, and no custom image was sent. A full install, recovery method, and Telnet activation remain unverified. The next transport investigation should determine whether the disconnect is a deliberate device stage transition, host `usbprint.sys` behavior, or a missing D4 flow-control exchange before trying more physical uploads.

The original printer image and the combined Wi-Fi/Telnet candidate remain local, ignored scratch artifacts. The candidate's signature is invalid under normal verification, even though its isolated controller length-gate path returned success; the live USB result does not validate that bypass.
