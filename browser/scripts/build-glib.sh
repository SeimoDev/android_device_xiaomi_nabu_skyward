#!/bin/sh
set -eu
cd /work
if ! test -f glib-2.90.1/glib/gmain.c; then
    python3 - <<'PY'
import tarfile
import urllib.request
urllib.request.urlretrieve('https://download.gnome.org/sources/glib/2.90/glib-2.90.1.tar.xz', 'glib-2.90.1.tar.xz')
with tarfile.open('glib-2.90.1.tar.xz') as archive:
    archive.extractall('.', filter='data')
PY
fi
if ! grep -q 'Some Android kernels backport pollable pidfds' glib-2.90.1/glib/gmain.c; then
    patch -d glib-2.90.1 -p1 < /browser/patches/glib-pidfd-waitid.patch
fi
meson setup --reconfigure glib-build glib-2.90.1 --cross-file=/browser/scripts/aarch64.ini \
    --prefix=/usr --libdir=lib/aarch64-linux-gnu --buildtype=release \
    -Dtests=false -Dinstalled_tests=false -Ddocumentation=false -Dman-pages=disabled \
    -Dintrospection=disabled -Dsysprof=disabled -Dselinux=disabled -Dlibmount=disabled -Dnls=disabled
ninja -C glib-build -j4 glib/libglib-2.0.so.0.9000.1
aarch64-linux-gnu-strip --strip-unneeded glib-build/glib/libglib-2.0.so.0.9000.1
mkdir -p build
cp glib-build/glib/libglib-2.0.so.0.9000.1 build/
