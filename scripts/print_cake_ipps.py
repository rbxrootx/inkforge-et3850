"""Send a prepared JPEG page to an ET-3850 over IPPS when explicitly requested.

The default mode only queries printer capabilities. Use --send to create a job.
"""

import argparse
import http.client
from pathlib import Path
import ssl
import struct
import time


def attr(tag: int, name: str, value: bytes | str) -> bytes:
    encoded_name = name.encode("ascii")
    encoded_value = value.encode("utf-8") if isinstance(value, str) else value
    return (
        bytes([tag])
        + struct.pack(">H", len(encoded_name))
        + encoded_name
        + struct.pack(">H", len(encoded_value))
        + encoded_value
    )


def packet(operation: int, request_id: int, attributes: bytes, document: bytes = b"") -> bytes:
    return struct.pack(">BBHI", 1, 1, operation, request_id) + b"\x01" + attributes + b"\x03" + document


def parse_ipp(data: bytes) -> tuple[int, dict[str, list[tuple[int, bytes]]]]:
    if len(data) < 9:
        raise ValueError("short IPP response")
    version_major, version_minor, status, _request_id = struct.unpack_from(">BBHI", data)
    if version_major != 1 or version_minor not in (0, 1):
        raise ValueError("unsupported IPP response version")
    values: dict[str, list[tuple[int, bytes]]] = {}
    pos = 8
    name = ""
    while pos < len(data):
        tag = data[pos]
        pos += 1
        if tag == 3:
            return status, values
        if tag <= 0x0F:
            continue
        if pos + 2 > len(data):
            break
        name_length = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        if pos + name_length + 2 > len(data):
            break
        if name_length:
            name = data[pos : pos + name_length].decode("utf-8", "replace")
        pos += name_length
        value_length = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        if pos + value_length > len(data):
            break
        values.setdefault(name, []).append((tag, data[pos : pos + value_length]))
        pos += value_length
    raise ValueError("truncated IPP attributes")


def first_text(values: dict[str, list[tuple[int, bytes]]], name: str) -> str | None:
    entries = values.get(name, [])
    return entries[0][1].decode("utf-8", "replace") if entries else None


def first_int(values: dict[str, list[tuple[int, bytes]]], name: str) -> int | None:
    entries = values.get(name, [])
    return struct.unpack(">I", entries[0][1])[0] if entries and len(entries[0][1]) == 4 else None


def exchange(host: str, body: bytes) -> tuple[int, dict[str, list[tuple[int, bytes]]]]:
    connection = http.client.HTTPSConnection(
        host, 631, timeout=30, context=ssl._create_unverified_context()
    )
    try:
        connection.request("POST", "/ipp/print", body, {"Content-Type": "application/ipp"})
        response = connection.getresponse()
        data = response.read()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} from IPPS endpoint")
        return parse_ipp(data)
    finally:
        connection.close()


def common_attrs(uri: str) -> bytes:
    return (
        attr(0x47, "attributes-charset", "utf-8")
        + attr(0x48, "attributes-natural-language", "en")
        + attr(0x45, "printer-uri", uri)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="printer IP address or DNS name")
    parser.add_argument("--image", type=Path, help="letter-size JPEG prepared for printing")
    parser.add_argument("--send", action="store_true", help="create a physical print job")
    args = parser.parse_args()
    uri = f"ipps://{args.host}:631/ipp/print"

    status, values = exchange(args.host, packet(0x000B, 1, common_attrs(uri)))
    if status != 0:
        raise RuntimeError(f"Get-Printer-Attributes IPP status 0x{status:04x}")
    model = first_text(values, "printer-make-and-model")
    state = first_int(values, "printer-state")
    formats = [value.decode("utf-8", "replace") for _, value in values.get("document-format-supported", [])]
    print(f"Printer: {model}; state: {state}; JPEG: {'image/jpeg' in formats}")
    if not args.send:
        print("Read-only capability check complete. No print job created.")
        return
    if not model or "ET-3850" not in model or "image/jpeg" not in formats:
        raise RuntimeError("printer identity or JPEG support did not match")
    if args.image is None:
        parser.error("--image is required with --send")
    document = args.image.read_bytes()
    if not document.startswith(b"\xff\xd8") or not document.endswith(b"\xff\xd9"):
        raise ValueError("--image is not a complete JPEG file")
    operation_attrs = (
        common_attrs(uri)
        + attr(0x42, "requesting-user-name", "Codex")
        + attr(0x42, "job-name", "Cake")
        + attr(0x49, "document-format", "image/jpeg")
    )
    status, values = exchange(args.host, packet(0x0002, 2, operation_attrs, document))
    if status != 0:
        raise RuntimeError(f"Print-Job IPP status 0x{status:04x}")
    job_id = first_int(values, "job-id")
    job_uri = first_text(values, "job-uri")
    print(f"Print-Job accepted: job-id={job_id}, job-uri={job_uri}")
    if job_id is None:
        return
    query_attrs = common_attrs(uri) + attr(0x21, "job-id", struct.pack(">I", job_id))
    for attempt in range(24):
        time.sleep(5)
        job_status, job = exchange(args.host, packet(0x0009, 3 + attempt, query_attrs))
        if job_status != 0:
            print(f"Get-Job-Attributes returned IPP 0x{job_status:04x}")
            return
        job_state = first_int(job, "job-state")
        print(f"Job {job_id} state: {job_state}")
        if job_state in (7, 8, 9):
            return


if __name__ == "__main__":
    main()
