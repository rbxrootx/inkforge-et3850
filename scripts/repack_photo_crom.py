"""Offline experiment: replace exactly one 320x240 PNG in ET-3850 UI CROM.

The output is a CROM region for further verification, not an installable image.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import zlib
import argparse


PNG_OFFSET = 0xB0E93C
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_end(blob: bytes, start: int = 0) -> int:
    if blob[start:start + 8] != PNG_SIGNATURE:
        raise ValueError("PNG signature missing")
    cursor = start + 8
    while True:
        size = struct.unpack_from(">I", blob, cursor)[0]
        kind = blob[cursor + 4:cursor + 8]
        cursor += 12 + size
        if kind == b"IEND":
            return cursor


def exact_png(data: bytes, expected_size: int) -> bytes:
    data = data[:png_end(data)]
    space = expected_size - len(data)
    if space < 20:
        raise ValueError(f"photo PNG needs {len(data)} bytes, slot has {expected_size}")
    payload = b"Comment\0" + b" " * (space - 12 - len(b"Comment\0"))
    kind = b"tEXt"
    chunk = struct.pack(">I", len(payload)) + kind + payload
    chunk += struct.pack(">I", zlib.crc32(kind + payload))
    result = data[:-12] + chunk + data[-12:]
    assert len(result) == expected_size and png_end(result) == expected_size
    return result


def code_maps(huffman: bytes) -> list[dict[int, tuple[int, int]]]:
    cursor = 0
    maps = []
    for expected in range(3):
        ident = huffman[cursor]
        assert ident == 0xF0 + expected
        cursor += 1
        counts = huffman[cursor:cursor + 16]
        cursor += 16
        table = {}
        code = 0
        for bits, quantity in enumerate(counts, 1):
            for symbol in huffman[cursor:cursor + quantity]:
                table[symbol] = code, bits
                code += 1
            cursor += quantity
            code <<= 1
        maps.append(table)
    assert cursor == len(huffman)
    return maps


def write_codes(items, maps):
    encoded = bytearray()
    value = 0
    length = 0
    for item in items:
        for table, symbol in zip(maps, item):
            code, bits = table[symbol]
            value = (value << bits) | code
            length += bits
            while length >= 8:
                length -= 8
                encoded.append((value >> length) & 255)
                value &= (1 << length) - 1
    if length:
        encoded.append(value << (8 - length))
    return bytes(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-crom", type=Path, required=True)
    parser.add_argument("--decoded-ui", type=Path, required=True)
    parser.add_argument("--wallpaper-png", type=Path, required=True)
    parser.add_argument("--uncrom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("uncrom", args.uncrom)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    raw = args.source_crom.read_bytes()
    original = args.decoded_ui.read_bytes()
    stock_end = png_end(original, PNG_OFFSET)
    stock_size = stock_end - PNG_OFFSET
    replacement = exact_png(args.wallpaper_png.read_bytes(), stock_size)
    desired = original[:PNG_OFFSET] + replacement + original[stock_end:]
    assert len(desired) == len(original)

    reader = decoder.CROMReader(io.BytesIO(raw))
    reader.read_data()
    reader.unpack_huffman_tables()
    reader.decompress_copy_items()
    first_block_end = reader.stream.tell()
    maps = code_maps(reader.huffman_table_data)
    available_lengths = sorted((control + 1 for control in maps[0] if control != 255), reverse=True)
    if 1 not in available_lengths:
        raise ValueError("Huffman table cannot encode a one-byte literal")

    new_items = []
    new_literal = bytearray()
    produced = bytearray()
    old_literal_at = 0
    copied_to_literal = 0
    for control, lo, hi in reader.copy_items:
        distance = lo | (hi << 8)
        if distance == 0 and control == 255:
            new_items.append((control, lo, hi))
            continue
        count = control + (2 if distance else 1)
        wanted = desired[len(produced):len(produced) + count]
        if not distance:
            old_literal_at += count
            new_items.append((control, 0, 0))
            new_literal.extend(wanted)
        else:
            pattern = bytes(produced[-distance:])
            would_copy = (pattern * ((count + distance - 1) // distance))[:count]
            if would_copy == wanted:
                new_items.append((control, lo, hi))
            else:
                copied_to_literal += count
                rest = count
                cursor = 0
                while rest:
                    piece = next(length for length in available_lengths if length <= rest)
                    new_items.append((piece - 1, 0, 0))
                    new_literal.extend(wanted[cursor:cursor + piece])
                    cursor += piece
                    rest -= piece
        produced.extend(wanted)
    assert produced == desired and old_literal_at == len(reader.literal_data)
    # The reference decoder always peeks 16 bits, including for the last
    # symbol; provide lookahead bytes after the final codeword.
    copy_data = write_codes(new_items, maps) + b"\0\0"

    pos = 10
    mark, length = struct.unpack_from(">HH", raw, pos)
    assert mark == 0xFFC4
    huffman_marker = raw[pos:pos + 2 + length]
    pos += 2 + length
    mark, length = struct.unpack_from(">HH", raw, pos)
    assert mark == 0xFFB1
    copy_info = raw[pos + 4:pos + 2 + length]
    assert len(copy_info) >= 9
    copy_info = copy_info[:1] + struct.pack(">II", len(copy_data), len(new_items)) + copy_info[9:]
    pos += 2 + length + len(reader.compressed_copy_data)
    mark, length = struct.unpack_from(">HH", raw, pos)
    assert mark == 0xFFB2 and length == 6
    assert pos + 2 + length + len(reader.literal_data) == first_block_end
    first = (raw[:10] + huffman_marker + struct.pack(">HH", 0xFFB1, len(copy_info) + 2) + copy_info + copy_data
             + struct.pack(">HHI", 0xFFB2, 6, len(new_literal)) + new_literal)
    candidate = first + raw[first_block_end:]
    growth = len(candidate) - len(raw)
    if growth > 0:
        if candidate[-growth:] != b"\xff" * growth:
            raise ValueError("CROM growth exceeds trailing filler")
        candidate = candidate[:-growth]
    else:
        candidate += b"\xff" * (-growth)
    assert len(candidate) == len(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(candidate)
    print("stock_png_bytes", stock_size, "photo_png_bytes", len(replacement))
    print("converted_copy_bytes", copied_to_literal, "old_items", len(reader.copy_items),
          "new_items", len(new_items))
    print("compressed_growth", growth, "output_sha256", hashlib.sha256(candidate).hexdigest())

    verify = decoder.CROMReader(io.BytesIO(candidate))
    restored = verify.unpack()
    assert restored == desired
    assert verify.stream.tell() == len(first)
    assert len(restored) == len(original)
    print("decoded_full_image_verified", True, "changed_interval", (PNG_OFFSET, stock_end))


if __name__ == "__main__":
    main()
