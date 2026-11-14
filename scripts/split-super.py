#!/usr/bin/env python3
"""Extract logical partitions from this ROM's raw super image (LP slot 0)."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def metadata(stream):
    stream.seek(4096)
    geometry = stream.read(52)
    if len(geometry) != 52 or struct.unpack_from("<II", geometry) != (0x616C4467, 52):
        raise ValueError("Expected a raw super image with LP geometry")
    if hashlib.sha256(geometry[:8] + bytes(32) + geometry[40:]).digest() != geometry[8:40]:
        raise ValueError("Invalid LP geometry checksum")
    max_size, slots, block = struct.unpack_from("<III", geometry, 40)
    if not (slots and max_size >= 256 and block == 4096):
        raise ValueError("Unsupported LP geometry")
    stream.seek(12288)
    header = stream.read(256)
    magic, major, minor, size = struct.unpack_from("<IHHI", header)
    if magic != 0x414C5030 or major != 10 or minor > 2 or size not in (128, 256):
        raise ValueError("Unsupported LP header")
    if hashlib.sha256(header[:12] + bytes(32) + header[44:size]).digest() != header[12:44]:
        raise ValueError("Invalid LP header checksum")
    tables_size = struct.unpack_from("<I", header, 44)[0]
    if size + tables_size > max_size:
        raise ValueError("LP tables exceed metadata capacity")
    stream.seek(12288 + size)
    tables = stream.read(tables_size)
    if hashlib.sha256(tables).digest() != header[48:80]:
        raise ValueError("Invalid LP table checksum")
    po, pn, ps = struct.unpack_from("<III", header, 80)
    eo, en, es = struct.unpack_from("<III", header, 92)
    if ps != 52 or es != 24 or po + pn * ps > tables_size or eo + en * es > tables_size:
        raise ValueError("Invalid partition/extent tables")
    result = []
    for i in range(pn):
        name, _, first, count, _ = struct.unpack_from("<36s4I", tables, po + i * ps)
        name = name.split(b"\0", 1)[0].decode()
        if not name or "/" in name or name in (".", "..") or first + count > en:
            raise ValueError("Invalid partition entry")
        extents = []
        for j in range(first, first + count):
            sectors, kind, sector, source = struct.unpack_from("<QIQI", tables, eo + j * es)
            if kind not in (0, 1) or source != 0:
                raise ValueError("Unsupported extent target")
            extents.append({"size": sectors * 512, "type": kind, "offset": sector * 512})
        result.append({"name": name, "extents": extents})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--partitions", nargs="+", default=["vendor_a", "odm_a", "system_a", "system_ext_a"])
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with args.image.open("rb") as stream:
        parts = metadata(stream)
        available = {p["name"] for p in parts}
        if set(args.partitions) - available:
            raise ValueError("Requested partition is absent")
        image_size = args.image.stat().st_size
        for part in parts:
            if part["name"] not in args.partitions:
                continue
            output = args.out / (part["name"] + ".img")
            with output.open("xb") as dest:
                for extent in part["extents"]:
                    remaining = extent["size"]
                    if extent["type"] == 1:
                        dest.seek(remaining, 1)
                        continue
                    if extent["offset"] + remaining > image_size:
                        raise ValueError("Super image is truncated")
                    stream.seek(extent["offset"])
                    while remaining:
                        data = stream.read(min(remaining, 8 * 1024 * 1024))
                        if not data:
                            raise ValueError("Truncated partition")
                        dest.write(data)
                        remaining -= len(data)
                dest.truncate()
            print(f"Extracted {output}", flush=True)
    (args.out / "partitions.json").write_text(json.dumps(parts, indent=2) + "\n")


if __name__ == "__main__":
    main()
