#!/bin/sh
set -eu
export PKG_CONFIG_SYSROOT_DIR=/work/sysroot
export PKG_CONFIG_LIBDIR=/work/sysroot/usr/lib/aarch64-linux-gnu/pkgconfig:/work/sysroot/usr/share/pkgconfig
mkdir -p /work/build
aarch64-linux-gnu-gcc --sysroot=/work/sysroot -O2 -Wall -Wextra -Werror /browser/src/browser.c -o /work/build/browser \
    $(pkg-config --cflags --libs wpe-webkit-2.0 wpe-platform-headless-2.0) \
    -Wl,-rpath-link,/work/sysroot/usr/lib/aarch64-linux-gnu
