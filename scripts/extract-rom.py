#!/usr/bin/env python3
"""Extract the supplied nabu ROM's boot and recovery dependencies, without mounting."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--out", required=True, type=Path, help="New empty extraction directory")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("Use an empty extraction directory")
    with zipfile.ZipFile(args.zip) as rom:
        for name in ("boot", "vendor_boot", "dtbo", "super"):
            with rom.open(f"images/{name}.img.zst") as source, (out / f"{name}.img").open("xb") as target:
                process = subprocess.Popen(["zstd", "-d", "-c"], stdin=subprocess.PIPE, stdout=target)
                try:
                    shutil.copyfileobj(source, process.stdin, 8 * 1024 * 1024)
                finally:
                    process.stdin.close()
                if process.wait():
                    raise RuntimeError(f"zstd failed for {name}")
            print(f"Extracted {name}.img", flush=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name("split-super.py")),
                    str(out / "super.img"), "--out", str(out / "partitions")], check=True)
    for name in ("vendor", "odm", "system", "system_ext"):
        subprocess.run(["fsck.erofs", f"--extract={out / name}", str(out / "partitions" / f"{name}_a.img")], check=True)
    vndk = out / "vndk30"
    (vndk / "root").mkdir(parents=True)
    with zipfile.ZipFile(out / "system_ext/apex/com.android.vndk.v30.apex") as apex:
        with apex.open("apex_payload.img") as source, (vndk / "payload.img").open("xb") as dest:
            shutil.copyfileobj(source, dest, 8 * 1024 * 1024)
    subprocess.run(["debugfs", "-R", f'rdump / "{vndk / "root"}"', str(vndk / "payload.img")], check=True)


if __name__ == "__main__":
    main()
