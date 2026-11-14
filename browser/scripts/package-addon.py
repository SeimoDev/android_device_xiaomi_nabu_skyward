#!/usr/bin/env python3
"""Package an assembled WPE root as a recovery-installable runtime ZIP."""
import argparse
from pathlib import Path
import tarfile
import tempfile
from zipfile import ZipFile, ZIP_STORED, ZipInfo

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('runtime', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='skyward-browser-') as tmp:
    packed = Path(tmp) / 'runtime.tar.gz'
    with tarfile.open(packed, 'w:gz') as tar:
        tar.add(args.runtime, arcname='.')
    with ZipFile(args.output, 'w', compression=ZIP_STORED) as archive:
        info = ZipInfo('META-INF/com/google/android/update-binary')
        info.external_attr = 0o100755 << 16
        archive.writestr(info, Path(__file__).with_name('update-binary').read_bytes())
        archive.write(packed, 'runtime.tar.gz')
print(args.output)
