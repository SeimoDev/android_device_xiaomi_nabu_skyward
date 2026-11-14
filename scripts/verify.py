#!/usr/bin/env python3
"""Verify the nabu image, kernel, ramdisk and unsigned AVB boot descriptor."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import struct
import tomllib
from prepare import boot_parts, read_cpio, extract


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--extract", type=Path)
    args = parser.parse_args()
    data = args.image.read_bytes()
    header, kernel, ramdisk = boot_parts(data)
    commandline = header[44:1580].split(b"\0", 1)[0].decode().split()
    boot_flags = [word for word in commandline if word.startswith("androidboot.fastboot=")]
    check(boot_flags == ["androidboot.fastboot=1"], "Missing nabu recovery fastboot flag")
    init_flags = [word for word in commandline if word.startswith("twrpfastboot=")]
    check(init_flags == ["twrpfastboot=1"], "Missing first-stage recovery override")
    _, original_kernel, original_ramdisk = boot_parts(args.source.read_bytes())
    check(kernel == original_kernel, "Kernel differs from supplied ROM")
    check(ramdisk.startswith(b"\x1f\x8b"), "Kernel requires gzip ramdisk")
    check(len(data) == 134217728, "Expected a 128 MiB boot image")
    entries = read_cpio(gzip.decompress(ramdisk))
    source = read_cpio(gzip.decompress(original_ramdisk))
    check(entries["system/bin/recovery"][1] == args.binary.read_bytes(), "Recovery binary mismatch")
    for path in ("system/bin/recovery", "system/bin/skyward-keymaster-compat", "system/bin/skyward-servicemanager", "system/bin/init", "system/bin/adbd"):
        check(stat.S_ISREG(entries[path][0][1]) and entries[path][0][1] & 0o111, f"Not executable: {path}")
    touch = [name for name in source if name.startswith("vendor/firmware/") and name.endswith(".bin")]
    check(len(touch) == 8, "Expected eight touch firmware files")
    for path in touch:
        check(entries["system/etc/firmware/" + path.removeprefix("vendor/firmware/")][1] == source[path][1], f"Firmware mismatch: {path}")
    manifest = json.loads((Path(__file__).parent / "materials.json").read_text())
    for item in manifest["files"]:
        actual = entries[item["destination"]][1]
        check(hashlib.sha256(actual).hexdigest() == item["sha256"], f"Material mismatch: {item['destination']}")
    configs = [d for name, (_, d) in entries.items() if name.endswith(".toml") and b'codename = "nabu"' in d]
    check(len(configs) == 1 and tomllib.loads(configs[0].decode())["device"]["ab"], "Missing nabu configuration")
    config = tomllib.loads(configs[0].decode())
    check(config["device"]["maintainer"] == {"name": "Seimo", "github": "https://github.com/SeimoDev", "x": "https://x.com/SeimoDev"}, "Incorrect device maintainer")
    check(config["device"]["recovery_in_boot"], "Missing boot installation support")
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(entries["system/etc/skyward/boot-installer.zip"][1])) as installer:
        check(installer.read("kernel.sha256") == hashlib.sha256(kernel).digest(), "Installer kernel mismatch")
        payload = read_cpio(gzip.decompress(installer.read("ramdisk.cpio.gz")))
        for line in installer.read("ramdisk.files").decode().splitlines():
            path, size, digest = line.split("\t")
            check(path in payload and payload[path][1] == b"", "Invalid installer file inventory")
            contents = entries[path][1]
            check(len(contents) == int(size) and hashlib.sha256(contents).hexdigest() == digest, "Installer file digest mismatch")
            payload[path] = (payload[path][0], contents)
        check(payload["system/bin/recovery"][1] == args.binary.read_bytes(), "Installer recovery binary mismatch")
        check("system/etc/skyward/boot-installer.zip" not in payload, "Nested installer payload")
    props = entries["prop.default"][1]
    check(b"ro.vndk.version=30\n" in props, "Wrong vendor runtime version")
    check(b"ro.skyward.binder.header=SYST\n" in props, "Binder header differs from the base libbinder")
    for name in (b"ro.build.version.release=", b"ro.build.version.security_patch=", b"ro.vendor.build.security_patch="):
        check(not any(line.startswith(name) for line in props.splitlines()), "Installed version must be adopted at runtime")
    check(not any(name.startswith("twres") for name in entries), "Old recovery assets remain")
    footer = data[-64:]
    check(footer[:4] == b"AVBf", "Missing AVB footer")
    original_size, offset, size = struct.unpack_from(">QQQ", footer, 12)
    vbmeta = data[offset:offset + size]
    check(vbmeta[:4] == b"AVB0" and struct.unpack_from(">I", vbmeta, 28)[0] == 0, "Expected unsigned vbmeta")
    auth_size = struct.unpack_from(">Q", vbmeta, 12)[0]
    descriptor_offset = struct.unpack_from(">Q", vbmeta, 96)[0]
    descriptor = vbmeta[256 + auth_size + descriptor_offset:]
    check(struct.unpack_from(">Q", descriptor)[0] == 2, "Expected hash descriptor")
    image_size = struct.unpack_from(">Q", descriptor, 16)[0]
    name_size, salt_size, digest_size = struct.unpack_from(">III", descriptor, 56)
    name = descriptor[132:132 + name_size]
    salt = descriptor[132 + name_size:132 + name_size + salt_size]
    digest = descriptor[132 + name_size + salt_size:132 + name_size + salt_size + digest_size]
    check(name == b"boot" and image_size == original_size, "Incorrect AVB partition or image size")
    check(hashlib.sha256(salt + data[:image_size]).digest() == digest, "AVB digest mismatch")
    report = {"image": args.image.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
              "header_version": struct.unpack_from("<I", header, 40)[0], "kernel_unchanged": True,
              "first_stage_recovery_override": True, "binder_header": "SYST",
              "compression": "gzip", "ramdisk_entries": len(entries), "touch_firmware": len(touch),
              "extra_materials": len(manifest["files"]), "avb_partition": name.decode(),
              "validation": "offline; hardware boot, touch, WLAN, USB and decryption require device testing"}
    args.image.with_suffix(".verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.extract:
        extract(entries, args.extract)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
