#!/usr/bin/env python3
"""Assemble the ELF dependency closure of the Skyward browser and its subprocesses."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from collections import deque

source_tree = Path(__file__).resolve().parents[1]
base = Path(os.environ.get("SKYWARD_WORKSPACE", Path.cwd())).resolve()
work = base / '.tools/wpe'
source = work / 'sysroot'
dest = work / 'browser-runtime'
if dest.exists():
    shutil.rmtree(dest)
dest.mkdir()
libs = source / 'usr/lib/aarch64-linux-gnu'
index = {p.name: p for p in libs.rglob('*.so*')}
queue = deque()
copied = set()

def resolve(path):
    for _ in range(20):
        if not path.is_symlink():
            return path
        target = Path(os.readlink(path))
        path = source / str(target).lstrip('/') if target.is_absolute() else path.parent / target
    raise RuntimeError(f'Symlink cycle: {path}')

def copy_elf(path):
    path = resolve(path)
    if path in copied:
        return
    copied.add(path)
    relative = path.relative_to(source)
    target = dest / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    queue.append(path)

def copy_dependency(name):
    if name not in index:
        raise RuntimeError(f'Missing library {name}')
    link = index[name]
    real = resolve(link)
    copy_elf(real)
    target = dest / link.relative_to(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target != dest / real.relative_to(source) and not target.exists():
        target.symlink_to(os.path.relpath(dest / real.relative_to(source), target.parent))

for folder in ('dev/shm', 'proc', 'sys', 'tmp/home', 'tmp/runtime', 'output', 'opt/wpe', 'etc/ssl/certs', 'downloads'):
    (dest / folder).mkdir(parents=True, exist_ok=True)
for name in ('null', 'random', 'urandom'):
    (dest / 'dev' / name).touch()
for name, target in [('lib', 'usr/lib'), ('bin', 'usr/bin'), ('dev/fd', '/proc/self/fd')]:
    (dest / name).symlink_to(target)
for folder in ('tmp', 'tmp/home', 'tmp/runtime', 'dev/shm', 'output'):
    os.chmod(dest / folder, 0o777 if folder != 'tmp' else 0o1777)
shutil.copy2(work / 'build/browser', dest / 'opt/wpe/browser')
shutil.copy2(source_tree / 'start.html', dest / 'opt/wpe/start.html')
queue.append(work / 'build/browser')
for name in ('WPEWebProcess', 'WPENetworkProcess', 'WPEGPUProcess'):
    copy_elf(libs / 'wpe-webkit-2.0' / name)
for path in (libs / 'wpe-webkit-2.0/injected-bundle').glob('*.so'):
    copy_elf(path)
copy_elf(libs / 'gio/modules/libgiognutls.so')
for name in ('libEGL.so.1', 'libEGL_mesa.so.0', 'libGLESv2.so.2'):
    copy_dependency(name)
copy_dependency('swrast_dri.so')
copy_elf(libs / 'ld-linux-aarch64.so.1')
(dest / 'usr/lib/ld-linux-aarch64.so.1').symlink_to('aarch64-linux-gnu/ld-linux-aarch64.so.1')
while queue:
    path = queue.popleft()
    dynamic = subprocess.check_output(['readelf', '-d', str(path)], text=True)
    for name in re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic):
        copy_dependency(name)

patched_glib = work / 'build/libglib-2.0.so.0.9000.1'
if patched_glib.exists():
    shutil.copy2(patched_glib, dest / 'usr/lib/aarch64-linux-gnu' / patched_glib.name)

gio = dest / 'usr/lib/aarch64-linux-gnu/gio/modules'
(gio / 'giomodule.cache').write_text('libgiognutls.so: gio-tls-backend\n')
shutil.copytree(source / 'etc/fonts', dest / 'etc/fonts', symlinks=True)
shutil.copytree(source / 'usr/share/glvnd', dest / 'usr/share/glvnd', symlinks=True)
fonts = dest / 'usr/share/fonts/truetype'
fonts.mkdir(parents=True)
shutil.copy2(base / 'skyward/resources/fonts/MiSansVF.ttf', fonts / 'MiSansVF.ttf')
shutil.copy2(source / 'usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', fonts / 'DejaVuSans.ttf')
shutil.copy2('/etc/ssl/certs/ca-certificates.crt', dest / 'etc/ssl/certs/ca-certificates.crt')
(dest / 'etc/nsswitch.conf').write_text('hosts: files dns\npasswd: files\ngroup: files\n')
(dest / 'etc/hosts').write_text('127.0.0.1 localhost\n::1 localhost\n')
(dest / 'etc/resolv.conf').write_text('nameserver 223.5.5.5\nnameserver 1.1.1.1\noptions timeout:2 attempts:2\n')
(dest / 'etc/passwd').write_text('nobody:x:65534:3003:Skyward browser:/tmp/home:/bin/false\n')
(dest / 'etc/group').write_text('inet:x:3003:\n')
(dest / 'etc/machine-id').write_text('9f15b10af8a24d38a49f5d3b98ef47a7\n')
os.chmod(dest, 0o755)
for p in dest.rglob('*'):
    if p.is_dir() and not p.is_symlink() and not str(p.relative_to(dest)).startswith(('tmp', 'output', 'dev/shm')):
        os.chmod(p, 0o755)
docs = dest / 'usr/share/doc/skyward-browser'
docs.mkdir(parents=True, exist_ok=True)
for name in ('LICENSE', 'README.md', 'dependencies.json'):
    shutil.copy2(source_tree / name, docs / name)
(docs / 'MiSans-NOTICE.txt').write_text(
    'MiSans: Copyright Xiaomi Inc. Font file supplied unchanged with Skyward.\n'
    'MiSans Font Intellectual Property License Agreement:\n'
    'https://hyperos.mi.com/font/download\n')
for copyright in (source / 'usr/share/doc').glob('*/copyright'):
    target = dest / 'usr/share/doc' / copyright.parent.name
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(copyright, target / 'copyright')
files = [p for p in dest.rglob('*') if p.is_file() and not p.is_symlink()]
manifest = {
    'engine': 'WPE WebKit 2.54.2 (Debian arm64)',
    'elf_objects': len(copied) + 1,
    'regular_files': len(files),
    'uncompressed_bytes': sum(p.stat().st_size for p in files),
    'largest_files': [{'path': str(p.relative_to(dest)), 'bytes': p.stat().st_size}
                      for p in sorted(files, key=lambda p: p.stat().st_size, reverse=True)[:12]],
}
(work / 'browser-runtime-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
