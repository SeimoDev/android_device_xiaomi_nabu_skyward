#!/usr/bin/env python3
"""Prepare the pinned Skyward source tree with the nabu adaptation."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def copy(source, destination):
    destination = Path(destination)
    if destination.exists():
        destination.chmod(0o644)
    shutil.copyfile(source, destination)
    destination.chmod(0o755 if destination.suffix == '.sh' else 0o644)
    return str(destination)


def prepare(out, upstream):
    lock = json.loads((ROOT / 'upstream.json').read_text())
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        run('git', 'clone', '--no-checkout', upstream or lock['url'], str(out))
        run('git', 'checkout', '--detach', lock['commit'], cwd=out)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=out, capture_output=True, text=True)
    if head.returncode or head.stdout.strip() != lock['commit']:
        if subprocess.check_output(['git', 'status', '--porcelain'], cwd=out).strip():
            raise RuntimeError('Skyward checkout has changes; use a new output directory')
        run('git', 'checkout', '--detach', lock['commit'], cwd=out)
    for patch in sorted((ROOT / 'patches').glob('*.patch')):
        check = subprocess.run(['git', 'apply', '--check', str(patch)], cwd=out, capture_output=True)
        if check.returncode == 0:
            run('git', 'apply', str(patch), cwd=out)
        else:
            applied = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=out, capture_output=True)
            if applied.returncode:
                raise RuntimeError(f'Patch does not apply: {patch.name}\n{check.stderr.decode()}')
    device = out / 'devices/nabu'
    device.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'scripts').iterdir():
        if path.is_file():
            copy(path, device / path.name)
    for path in (ROOT / 'helpers').glob('*.c'):
        copy(path, device / path.name)
    shutil.copytree(ROOT / 'recovery/root', device / 'overlay', dirs_exist_ok=True, copy_function=copy)
    for directory in (device, device / 'overlay', *(device / 'overlay').rglob('*')):
        if directory.is_dir():
            directory.chmod(0o755)
    copy(ROOT / 'nabu.toml', out / 'devices/nabu.toml')
    copy(ROOT / 'docs/PORTING.md', device / 'README.md')
    copy(ROOT / 'materials.json', device / 'materials.json')
    print(f'Prepared Skyward {lock["version"]} for nabu: {out}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'work/skyward')
    parser.add_argument('--upstream', help='Alternative Git mirror, checked against upstream.json')
    args = parser.parse_args()
    prepare(args.out.resolve(), args.upstream)


if __name__ == '__main__':
    main()
