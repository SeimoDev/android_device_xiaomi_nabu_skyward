#!/usr/bin/env python3
"""Extract nabu's recovery-as-boot image and prepare its Skyward base."""
import argparse
import gzip
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct


def align(n, unit=4):
    return (n + unit - 1) // unit * unit


def boot_parts(data):
    if data[:8] != b"ANDROID!" or len(data) < 4096:
        raise ValueError("Expected an Android boot image")
    version = struct.unpack_from("<I", data, 40)[0]
    if version not in (3, 4):
        raise ValueError(f"Expected a v3/v4 nabu boot image, got v{version}")
    kernel_size, ramdisk_size = struct.unpack_from("<II", data, 8)
    start = 4096 + align(kernel_size, 4096)
    if start + ramdisk_size > len(data):
        raise ValueError("Truncated boot image")
    return data[:4096], data[4096:4096 + kernel_size], data[start:start + ramdisk_size]


def read_cpio(data):
    entries, offset = {}, 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        if header[:6] != b"070701":
            raise ValueError(f"Invalid newc header at {offset}")
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        size, namesize = fields[6], fields[11]
        name_end = offset + 110 + namesize
        if not namesize or name_end > len(data) or data[name_end - 1] != 0:
            raise ValueError("Truncated cpio name")
        name = data[offset + 110:name_end - 1].decode()
        offset = align(name_end)
        end = offset + size
        if end > len(data):
            raise ValueError(f"Truncated cpio data: {name}")
        contents = data[offset:end]
        offset = align(end)
        if name == "TRAILER!!!":
            return entries
        parts = PurePosixPath(name)
        if not name or parts.is_absolute() or ".." in parts.parts or str(parts) != name:
            raise ValueError(f"Unsafe archive path: {name}")
        if name in entries:
            raise ValueError(f"Duplicate archive path: {name}")
        entries[name] = (fields, contents)
    raise ValueError("Missing cpio trailer")


def archive(entries):
    result = bytearray()
    for name, (fields, data) in list(entries.items()) + [("TRAILER!!!", ([0] * 13, b""))]:
        fields = fields.copy()
        encoded = name.encode() + b"\0"
        fields[6], fields[11], fields[12] = len(data), len(encoded), 0
        result.extend(b"070701" + b"".join(f"{x:08x}".encode() for x in fields))
        result.extend(encoded)
        result.extend(b"\0" * (align(len(result)) - len(result)))
        result.extend(data)
        result.extend(b"\0" * (align(len(result)) - len(result)))
    return bytes(result)


def add(entries, name, data=b"", mode=stat.S_IFREG | 0o644):
    parent = str(PurePosixPath(name).parent)
    if parent != ".":
        if parent not in entries:
            add(entries, parent, mode=stat.S_IFDIR | 0o755)
        elif not stat.S_ISDIR(entries[parent][0][1]):
            raise ValueError(f"Archive parent is not a directory: {parent}")
    fields = [len(entries) + 100000, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name.encode()) + 1, 0]
    entries[name] = (fields, data)


def image(header, kernel, ramdisk):
    header = bytearray(header)
    struct.pack_into("<II", header, 8, len(kernel), len(ramdisk))
    if struct.unpack_from("<I", header, 40)[0] == 4:
        struct.pack_into("<I", header, 1580, 0)
    result = header + kernel
    result.extend(b"\0" * (align(len(result), 4096) - len(result)))
    result.extend(ramdisk)
    result.extend(b"\0" * (align(len(result), 4096) - len(result)))
    return result


def recovery_header(header):
    header = bytearray(header)
    cmdline = header[44:1580].split(b"\0", 1)[0].decode()
    settings = {
        # The reused TWRP first-stage init checks this before force_normal_boot.
        # androidboot.fastboot alone does not prevent switching into Android.
        "twrpfastboot": "1",
        "androidboot.fastboot": "1",
        "androidboot.selinux": "permissive",
        "firmware_class.path": "/system/etc/firmware",
    }
    words = [word for word in cmdline.split() if word.split("=", 1)[0] not in settings]
    words.extend(f"{key}={value}" for key, value in settings.items())
    encoded = " ".join(words).encode()
    if len(encoded) >= 1536:
        raise ValueError("Kernel command line is too long")
    header[44:1580] = encoded.ljust(1536, b"\0")
    return header


def extract(entries, out):
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError(f"Extraction destination must be empty: {out}")
    links = []
    for name, (fields, data) in entries.items():
        path = out / name
        for parent in PurePosixPath(name).parents:
            if str(parent) != "." and parent.as_posix() in entries:
                if not stat.S_ISDIR(entries[parent.as_posix()][0][1]):
                    raise ValueError(f"Entry below a non-directory: {name}")
        mode = fields[1]
        if stat.S_ISDIR(mode):
            path.mkdir(parents=True, exist_ok=True)
        elif stat.S_ISREG(mode):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(mode & 0o777)
        elif stat.S_ISLNK(mode):
            links.append((path, data.decode()))
    for path, target in links:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)


def prepare(entries, overlay):
    props = entries.get("prop.default", (None, b""))[1]
    if b"ro.product.system.device=nabu\n" not in props:
        raise ValueError("Base ramdisk does not identify nabu")
    # The base supplies Android init, its libraries, policy and utilities.
    # Skyward owns the recovery service, USB MTP and key-service startup.
    removed = ("twres", "res/images", "system/etc/terminfo", "system/etc/nano")
    replaced_commands = {f"system/bin/{s}" for s in ("7za", "avbctl", "resetprop", "unzip", "zstd")}
    for name in list(entries):
        if (any(name == p or name.startswith(p + "/") for p in removed)
                or name in replaced_commands
                or "twrp" in name.lower()
                or name.startswith(("ramdisk-files", "init.recovery.qcom_decrypt", "init.recovery.services.qcom_decrypt"))
                or name in ("system/bin/prepdecrypt.sh", "system/bin/overrideprops.sh",
                            "system/etc/init/keystore2.rc", "system/etc/init/hwservicemanager.rc")):
            del entries[name]
    init_path = "system/etc/init/hw/init.rc"
    init = entries[init_path][1].decode().replace("setprop sys.usb.configfs 0", "setprop sys.usb.configfs 1")
    add(entries, init_path, init.encode())
    manager_rc = "system/etc/init/servicemanager.rc"
    manager = entries[manager_rc][1].replace(
        b"service servicemanager /system/bin/servicemanager",
        b"service servicemanager /system/bin/skyward-servicemanager")
    add(entries, manager_rc, manager)
    # This port's vendor is VNDK 30; the recovery base was built with 32.
    props = re.sub(rb"(?m)^ro\.vndk\.version=.*$", b"ro.vndk.version=30", props)
    # This base's libbinder writeInterfaceToken uses the SYST variant.
    props = re.sub(rb"(?m)^ro\.skyward\.binder\.header=.*\n?", b"", props)
    props = props.rstrip(b"\n") + b"\nro.skyward.binder.header=SYST\n"
    add(entries, "prop.default", props)
    # Firmware remains visible after Skyward mounts the installed vendor.
    for name, (_, data) in list(entries.items()):
        if name.startswith("vendor/firmware/") and name.endswith(".bin"):
            add(entries, "system/etc/firmware/" + name.removeprefix("vendor/firmware/"), data)
    for path in sorted(overlay.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Overlay must contain regular files: {path}")
        if path.is_file():
            relative = path.relative_to(overlay).as_posix()
            add(entries, relative, path.read_bytes(),
                stat.S_IFREG | (0o755 if relative.startswith("system/bin/") or path.suffix == ".sh" else 0o644))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--extract", type=Path, help="Empty directory for the original ramdisk")
    parser.add_argument("--overlay", type=Path, default=Path(__file__).resolve().parent / "overlay")
    args = parser.parse_args()
    data = args.boot.read_bytes()
    header, kernel, compressed = boot_parts(data)
    entries = read_cpio(gzip.decompress(compressed))
    args.out.mkdir(parents=True, exist_ok=True)
    if args.extract:
        extract(entries, args.extract)
    (args.out / "kernel").write_bytes(kernel)
    (args.out / "recovery-ramdisk.cpio.gz").write_bytes(compressed)
    (args.out / "recovery-source.img").write_bytes(image(header, kernel, compressed))
    start = kernel.find(b"IKCFG_ST")
    if start >= 0:
        end = kernel.index(b"IKCFG_ED", start)
        (args.out / "kernel.config").write_bytes(gzip.decompress(kernel[start + 8:end]))
    version = re.search(rb"Linux version [^\x00\n]+", kernel)
    manifest = {"source": str(args.boot), "header_version": struct.unpack_from("<I", header, 40)[0],
                "kernel": version[0].decode() if version else "unknown", "files": [
                    {"path": n, "mode": oct(f[1]), "size": len(d)} for n, (f, d) in entries.items()]}
    (args.out / "source.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    prepared = prepare(entries, args.overlay)
    header = recovery_header(header)
    packed = gzip.compress(archive(prepared), compresslevel=9, mtime=0)
    (args.out / "prepared-base.img").write_bytes(image(header, kernel, packed))
    print(f"Prepared {args.out / 'prepared-base.img'} ({len(prepared)} ramdisk entries)")


if __name__ == "__main__":
    main()
