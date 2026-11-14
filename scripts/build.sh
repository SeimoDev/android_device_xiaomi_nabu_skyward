#!/usr/bin/env bash
set -euo pipefail
device_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$device_dir/../.." && pwd)
workspace_dir=$(cd -- "$repo_dir/.." && pwd)
rom_dir=${1:-"$workspace_dir/reference/rom"}
output_dir=${2:-"$workspace_dir/out"}
rom_dir=$(realpath "$rom_dir")
mkdir -p "$output_dir"
output_dir=$(realpath "$output_dir")

# The local toolchain is optional; a normal Rust/NDK installation also works.
if [[ -x "$workspace_dir/.tools/cargo/bin/cargo" ]]; then
    export CARGO_HOME="$workspace_dir/.tools/cargo"
    export RUSTUP_HOME="$workspace_dir/.tools/rustup"
    export PATH="$CARGO_HOME/bin:$workspace_dir/.tools/local/usr/bin:$PATH"
fi
export ANDROID_NDK_HOME=${ANDROID_NDK_HOME:-"$workspace_dir/.tools/android-ndk-r29"}
host_target=${SKYWARD_HOST_TARGET:-/tmp/skyward-nabu-target}
android_target=${SKYWARD_ANDROID_TARGET:-/tmp/skyward-nabu-android}
init_target=${SKYWARD_INIT_TARGET:-/tmp/skyward-nabu-system-init}
clang="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
[[ -x "$clang" ]] || { echo "Set ANDROID_NDK_HOME to NDK r29" >&2; exit 1; }
cd "$repo_dir"

# Extract the recovery materials once. The original compressed ramdisk and
# kernel are retained separately from the prepared base.
if [[ ! -d "$output_dir/nabu/source-root" ]]; then
    python3 "$device_dir/prepare.py" --boot "$rom_dir/boot.img" \
        --out "$output_dir/nabu" --extract "$output_dir/nabu/source-root"
fi
python3 "$device_dir/collect.py" --vendor "$rom_dir/vendor" \
    --vndk "$rom_dir/vndk30/root" --base "$output_dir/nabu/source-root"
"$clang" -Os -Wall -Wextra -Werror -fPIE -pie -Wl,--strip-all \
    "$device_dir/keymaster-compat.c" -ldl -o "$device_dir/overlay/system/bin/skyward-keymaster-compat"
"$clang" -Os -Wall -Wextra -Werror -fPIE -pie -Wl,--strip-all \
    "$device_dir/servicemanager.c" -o "$device_dir/overlay/system/bin/skyward-servicemanager"
"$clang" -Os -Wall -Wextra -Werror -fPIE -pie -Wl,--strip-all \
    "$device_dir/browser-runner.c" -o "$device_dir/overlay/system/bin/skyward-browser"
python3 "$device_dir/prepare.py" --boot "$rom_dir/boot.img" --out "$output_dir/nabu"

CARGO_TARGET_DIR="$host_target" cargo build --locked --release -p skyward-pack
CARGO_TARGET_DIR="$android_target" cargo ndk -t arm64-v8a --platform 30 build --locked --release -p skyward
CARGO_TARGET_DIR="$init_target" RUSTFLAGS='-C target-feature=+crt-static' \
    cargo ndk -t arm64-v8a --platform 30 build --locked --release -p skyward-system-init
binary="$android_target/aarch64-linux-android/release/skyward"
system_init="$init_target/aarch64-linux-android/release/system-init"
"$host_target/release/skyward-pack" recovery --base "$output_dir/nabu/prepared-base.img" \
    --partition-size 134217728 --partition-name boot --binary "$binary" --system-init "$system_init" \
    --config "$repo_dir/devices/nabu.toml" --font "$repo_dir/resources/fonts/MiSansVF.ttf" \
    --mono "$repo_dir/resources/fonts/KirkMono-Regular.ttf" --mono-license "$repo_dir/resources/fonts/KirkMono-OFL.txt" \
    --out "$output_dir/skyward-nabu-boot.img"
python3 "$device_dir/verify.py" "$output_dir/skyward-nabu-boot.img" --source "$rom_dir/boot.img" --binary "$binary"
mkdir -p "$output_dir/bin"
cp "$binary" "$system_init" "$host_target/release/skyward-pack" "$output_dir/bin/"
chmod 755 "$output_dir/bin/"*
(cd "$output_dir" && sha256sum skyward-nabu-boot.img > SHA256SUMS)
chmod 644 "$output_dir/skyward-nabu-boot.img" "$output_dir/skyward-nabu-boot.verification.json" \
    "$output_dir/SHA256SUMS" "$output_dir/nabu/"*.img "$output_dir/nabu/"*.json \
    "$output_dir/nabu/kernel" "$output_dir/nabu/kernel.config" "$output_dir/nabu/recovery-ramdisk.cpio.gz"
