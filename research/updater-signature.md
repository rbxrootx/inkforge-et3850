# Windows updater and RCX signature trace

The official XB22Q5 recovery package bundles `EPFWUPD.exe` and `FWCJ61TL.rcx`. The executable is a generic Epson updater with several HTTP transports. Decompilation below refers to the copy bundled with that package; the presence of a generic path does not prove that the ET-3850 exposes it in normal mode.

## Network transport code

At `EPFWUPD.exe` address `0x4343fc`, the firmware POST flow selects `/data_check.cgi` when its HTTP type field is `0` and `/firmwareupdate/checknew` when it is `1`. After a successful check, it posts again to the matching write endpoint, including `/firmwareupdate/writenew` for type `1`. The type accessor at `0x43835e` reads a field at object offset `0x64`; setter `0x43835a` changes it. In the connect function at `0x433f70`, the updater sets type `0`, requests `/dnver.htm`, then switches to type `1` and retries after a non-2xx response. This is a transport fallback, not proof that a given printer accepts type `1` uploads. Further model selection still needs tracing.

The same executable includes `/FIRMWAREUPDATE`, `/FIRMWAREUPDATE/ADMINCHECK`, and `/DOWN/FIRMWAREUPDATE/{MAIN,NET,ROM1,ROM2}`. On the extracted ET-3850 `nwsoc` application, `/FIRMWAREUPDATE` is present, but the lowercase `checknew` and `writenew` strings are absent. Prior HEAD requests to those lowercase routes and a GET of `/dnver.htm` on the live printer returned 404. This is evidence against assuming the generic updater's type `1` HTTP route is active on this model; it is not a complete test of recovery mode or other transport methods.

The `nwsoc` handler referencing uppercase `/FIRMWAREUPDATE` at `0x16de88` performs update preparation through controller calls and service-state changes. It does not expose a plain file-upload handler in the decompiled path. A prior unauthenticated GET of that route returned 200 once and later 500 while the printer stayed reachable. Its stateful behavior means repeated GET probes would not be a harmless endpoint check. This observation alone does not establish an authorization flaw or sustained denial of service.

## Signature format and verification paths

The updater resolves `BCryptVerifySignature` dynamically with `GetProcAddress` at `0x44904b`; it is **not** a PE import. At `0x44a891`, it computes SHA-256 over a selected image segment. When the segment begins with `EPSONSIGN`, it skips the first 4096 bytes before hashing. At `0x44abe4`, it imports a 72-byte `ECCPUBLICBLOB` and verifies a 64-byte signature with `ECDSA_P256`. The caller at `0x449fca` sets an error when verification fails. This establishes a signature gate for packages selected by that code path. We have not run the updater with a modified image or proved that XB20 selects it.

The XB22Q5 RCX has `EPSONSIGNXB20d` at offset `0x112`. Its 4096-byte block declares a payload length of 40,603,648 bytes, exactly the bytes from offset `0x1112` through end of file. The 64-byte signature at offset `0x132` verifies as ECDSA P-256 over the SHA-256 digest of that payload, `e42260723d29823a0bcef45cde2f71f619968b8c94d9f1ebdb92c344c5d98ef3`. The matching public key coordinates are embedded in the same RCX at offset `0xb122` (under an `XB05` marker). Reproduce the layout with [`inspect_signature_block.py`](../scripts/inspect_signature_block.py), or the cryptographic check with [`verify_rcx_signature.py`](../scripts/verify_rcx_signature.py) and the `cryptography` Python package. Both require a separately obtained official RCX. A public key inside the signed image establishes internal consistency; it does not by itself establish the device's trusted key.

The updater's compiled ECDSA key table at `0x660764` contains filename patterns ranging across FY14–FY21. None names the XB20 family, and none of its listed public keys verifies this RCX signature. [`check_updater_key_table.py`](../scripts/check_updater_key_table.py) reproduces both checks against the matching updater and RCX. Therefore the decompiled host verification path cannot yet be claimed as the gate for this ET-3850 package. Another verification path or device-side enforcement may apply.

## Remaining installation questions

1. Trace the HTTP type assignment and model feature selection to learn whether the ET-3850 ever uses the generic network POST path.
2. Trace the XB20-specific updater path and determine whether it checks the signature or passes the RCX to the printer.
3. Determine whether the printer's controller or boot process independently rejects a modified payload. The extracted Linux application alone does not answer that question.
4. Establish a recovery route before testing any modified upload on the physical printer, which currently has no USB connection.

No new vulnerability is confirmed by the existence of these endpoints or the signature block. No firmware bytes were sent to the printer in this trace.
