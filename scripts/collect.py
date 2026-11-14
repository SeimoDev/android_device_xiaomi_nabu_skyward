#!/usr/bin/env python3
"""Collect nabu firmware and missing ELF dependencies from the supplied ROM."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def needed(path):
    output = subprocess.check_output(["readelf", "-d", str(path)], text=True)
    return re.findall(r"\(NEEDED\).*\[(.*?)\]", output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", required=True, type=Path)
    parser.add_argument("--vndk", required=True, type=Path, help="Extracted VNDK 30 APEX root")
    parser.add_argument("--base", required=True, type=Path, help="Extracted recovery ramdisk")
    parser.add_argument("--overlay", type=Path, default=Path(__file__).resolve().parent / "overlay")
    args = parser.parse_args()
    records = []

    def copy(source, destination):
        if source.is_symlink():
            raise ValueError(f"Expected a regular ROM file: {source}")
        data = source.read_bytes()
        out = args.overlay / destination
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        out.chmod(0o644)
        origin = ("vendor/" + source.relative_to(args.vendor).as_posix()
                  if source.is_relative_to(args.vendor)
                  else "vndk30/root/" + source.relative_to(args.vndk).as_posix())
        records.append({"source": origin, "destination": destination,
                        "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    files = sorted(p for p in (args.vendor / "firmware").iterdir()
                   if p.name.startswith(("a630_", "a640_", "ipa_fws.", "ipa_uc.")))
    if not files:
        raise ValueError("No nabu GPU/IPA firmware in vendor")
    for source in files:
        copy(source, "system/etc/firmware/" + source.name)
    copy(args.vendor / "etc/wifi/WCNSS_qcom_cfg.ini", "system/etc/firmware/wlan/qca_cld/WCNSS_qcom_cfg.ini")

    # Keep the recovery's bionic/binder libraries together. Add only libraries
    # absent from that base, following the vendor's dependency graph.
    search = [args.base / "system/lib64", args.vendor / "lib64", args.vndk / "lib64"]
    queue = [args.vendor / p for p in (
        "bin/hw/wpa_supplicant", "bin/cnss-daemon", "bin/qrtr-ns", "bin/irsc_util",
        "bin/pd-mapper", "bin/pm-service", "bin/pm-proxy",
        "bin/rmt_storage", "bin/tftp_server",
        "bin/qseecomd", "bin/ssgtzd", "bin/hw/android.hardware.keymaster@4.1-service-qti",
        "bin/hw/android.hardware.gatekeeper@1.0-service-qti", "bin/hw/android.hardware.boot-service.nabu")]
    seen = set()
    while queue:
        binary = queue.pop(0)
        for name in needed(binary):
            if name in seen:
                continue
            seen.add(name)
            source = next((directory / name for directory in search if (directory / name).is_file()), None)
            if source is None:
                raise ValueError(f"Unresolved dependency: {binary}: {name}")
            if source.parent != search[0]:
                copy(source, "system/lib64/" + name)
            queue.append(source)
    manifest = args.overlay.parent / "materials.json"
    manifest.write_text(json.dumps({"files": records}, ensure_ascii=False, indent=2) + "\n")
    print(f"Collected {len(records)} files; resolved {len(seen)} shared libraries")


if __name__ == "__main__":
    main()
