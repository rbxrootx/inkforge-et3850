"""Connect to the owner's password-gated ET3850MOD root shell on TCP 2323."""

from __future__ import annotations

from pathlib import Path
import secrets
import sys
import telnetlib
import time


PROMPT = b"ET3850MOD Password:"


def _collect(client: telnetlib.Telnet, seconds: float, marker: bytes | None = None) -> bytes:
    output = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(0.1)
        try:
            output.extend(client.read_very_eager())
        except EOFError:
            break
        if b"Login incorrect" in output or (marker and marker in output):
            break
    return bytes(output)


def connect(host: str, password_file: Path, command: str | None = None) -> dict | None:
    """Authenticate with a local secret; return command output or take over the terminal."""
    secret = password_file.read_bytes().strip()
    if not secret or b"\n" in secret or b"\r" in secret:
        raise ValueError("password file must contain one nonempty line")
    with telnetlib.Telnet(host, 2323, timeout=5) as client:
        greeting = client.read_until(PROMPT, timeout=5)
        if PROMPT not in greeting:
            raise RuntimeError("ET3850MOD login prompt was not found on port 2323")
        client.write(secret + b"\n")
        initial = _collect(client, 1.5)
        if b"Login incorrect" in initial:
            raise RuntimeError("private ET3850MOD password was rejected")
        client.write(b"stty -echo\n")
        _collect(client, 0.25)
        if command is None:
            print(f"Connected to {host}:2323. Use 'exit' to close the shell.")
            if initial:
                sys.stdout.write(initial.replace(secret, b"[REDACTED]").decode("utf-8", "replace"))
                sys.stdout.flush()
            client.mt_interact()
            return None
        token = secrets.token_hex(8).encode()
        marker = b"__ET3850_DONE_" + token + b"__"
        client.write(command.encode("utf-8") + b"\n")
        # Split the marker so the terminal's echoed command cannot satisfy the read.
        client.write(b"printf '\n__ET3850_DONE_%s__\n' " + token + b"\n")
        response = _collect(client, 10, marker)
        client.write(b"exit\n")
    safe = response.replace(secret, b"[REDACTED]")
    if marker not in safe:
        raise TimeoutError("command did not complete before the ten-second timeout")
    return {"host": host, "port": 2323, "output": safe.split(marker, 1)[0].decode("utf-8", "replace")}
