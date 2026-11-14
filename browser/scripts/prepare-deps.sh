#!/bin/sh
set -eu
cd "${SKYWARD_WORKSPACE:-$(dirname "$0")/../..}"
WPE_WORK="$(pwd)/.tools/wpe"
mkdir -p "$WPE_WORK/apt/etc/apt/preferences.d" \
    "$WPE_WORK/apt/var/lib/apt/lists/partial" \
    "$WPE_WORK/apt/var/cache/apt/archives/partial" \
    "$WPE_WORK/apt/var/lib/dpkg" "$WPE_WORK/sysroot"
touch "$WPE_WORK/apt/var/lib/dpkg/status"
cat > "$WPE_WORK/apt/etc/apt/sources.list" <<'EOF'
deb [arch=arm64 signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian sid main
EOF
cat > "$WPE_WORK/apt.conf" <<EOF
Dir "$WPE_WORK/apt";
Dir::Etc::sourcelist "sources.list";
Dir::Etc::sourceparts "-";
Dir::State::status "$WPE_WORK/apt/var/lib/dpkg/status";
APT::Architecture "arm64";
APT::Architectures { "arm64"; };
Acquire::Languages "none";
Debug::NoLocking "true";
APT::Install-Recommends "false";
APT::Install-Suggests "false";
EOF
apt-get -c "$WPE_WORK/apt.conf" update
apt-get -c "$WPE_WORK/apt.conf" --assume-yes --download-only install \
    libwpewebkit-2.0-dev=2.54.2-1+b1 libegl-mesa0 libgles2 fonts-dejavu-core ca-certificates
for package in "$WPE_WORK"/apt/var/cache/apt/archives/*.deb; do
    dpkg-deb -x "$package" "$WPE_WORK/sysroot"
done
for name in lib bin sbin; do
    if ! test -e "$WPE_WORK/sysroot/$name"; then
        ln -s "usr/$name" "$WPE_WORK/sysroot/$name"
    fi
done
