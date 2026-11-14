# Skyward Recovery device configuration for Xiaomi Pad 5 (nabu)

Unofficial Skyward 0.3.1 port for **Xiaomi Pad 5 / nabu**, maintained by **Seimo**.

[Downloads](https://github.com/SeimoDev/android_device_xiaomi_nabu_skyward/releases) · [GitHub](https://github.com/SeimoDev) · [X](https://x.com/SeimoDev) · [Skyward upstream](https://github.com/kirklin/skyward)

## Device

| Item | Configuration |
| --- | --- |
| Device | Xiaomi Pad 5 (`nabu`) |
| SoC | Snapdragon 860 / SM8150 |
| Display | 1600 × 2560 LCD, 360 dpi |
| Layout | A/B, recovery-as-boot, 128 MiB boot partition |
| Kernel | ROM-provided `4.14.180-moon-os3-ga5805c039` |
| Tested ROM | `HyperOS_4.0.0.41_nabu_A17_by_zxcwsurx_20260920.zip` |
| Vendor runtime | VNDK 30 |
| Maintainer | Seimo — [GitHub](https://github.com/SeimoDev), [X](https://x.com/SeimoDev) |

## Status

Display, touch, root ADB, MTP session, Wi-Fi scanning, Wi-Fi connection and internet access have been tested on the tablet. The supplied ROM's unencrypted F2FS `/data` opens successfully, and the existing internal-storage files are accessible through the file manager. The About page displays the device maintainer and public profile URLs. The Install page provides an **Install Skyward to boot** entry for the current slot.

The ROM disables file and metadata encryption. Credential-based FBE decryption on other ROMs is unverified; SharedSecret negotiation on this vendor returns error `-38`. Other ROM versions require their own hardware validation. The image uses the recovery base's permissive SELinux and root ADB configuration.

## Browser and advanced networking

The home page includes a **Browser** entry below WLAN. Install the separate `skyward-browser-runtime.zip` component in Skyward to provide WPE WebKit, then open the browser from the home page. Its address bar, touch input, keyboard and navigation controls are integrated into the recovery. Downloads are saved in `/sdcard/Download/Skyward`; the Downloads button opens that folder.

**WLAN → Advanced network settings** provides HTTP CONNECT / SOCKS5 proxy settings and automatic / manual DNS. The browser takes these settings when it starts. Browser sources, runtime build instructions and current limitations are in [browser/README.md](browser/README.md).

## Source layout

This is a standalone Skyward device repository. Skyward uses a Rust workspace and TOML device configuration. The `patches/` directory contains all recovery changes relative to the pinned upstream commit.

```text
nabu.toml                 Device and maintainer configuration
upstream.json             Skyward commit and toolchain versions
patches/                  Recovery platform and About-page changes
recovery/root/            Recovery init and USB configuration
helpers/                  Keymaster, servicemanager and browser launchers
scripts/                  ROM extraction, dependency collection and image packing
browser/                  WPE bridge, start page and optional runtime build
proprietary-files.txt     ROM extraction inventory with SHA-256 digests
materials.json            File provenance and destinations
kernel/nabu.config        Configuration extracted from the ROM kernel
bootstrap.py              Prepare the matching Skyward source tree
extract-files.sh          Extract the supplied ROM
build.sh                  Build the recovery image
```

## Build

Use Linux with Git, Python 3.11+, `zstd`, `erofs-utils`, `e2fsprogs`, and `binutils`. Install Rust **1.100.0** with the `aarch64-linux-android` target, **NDK r29**, and `cargo-ndk` **4.1.2**. Allow at least 40 GiB of free space for the extracted ROM and build outputs.

```bash
git clone https://github.com/SeimoDev/android_device_xiaomi_nabu_skyward.git
cd android_device_xiaomi_nabu_skyward

rustup toolchain install 1.100.0 --profile minimal --component clippy --target aarch64-linux-android
cargo +1.100.0 install cargo-ndk --version 4.1.2 --locked
export ANDROID_NDK_HOME=/path/to/android-ndk-r29

./extract-files.sh /path/to/HyperOS_4.0.0.41_nabu_A17_by_zxcwsurx_20260920.zip
./build.sh
```

The build prepares `work/skyward` at the exact commit in `upstream.json`, applies the patches, extracts the base ramdisk and dependencies, compiles the helper programs and recovery, and verifies the boot image. The resulting image is `out/skyward-nabu-boot.img`. To use an already extracted ROM:

```bash
./build.sh /path/to/extracted/rom /path/to/output
```

The ROM supplies the prebuilt kernel and original recovery environment. The device sources, helper sources and upstream patches are available here; see [NOTICE](NOTICE) for component provenance and licenses. [Porting notes](docs/PORTING.md) describe the platform changes.

## Boot

On an unlocked nabu with the tested ROM installed, temporarily boot the downloaded image:

```bash
fastboot boot skyward-nabu-boot.img
```

Unencrypted internal storage opens automatically. Use **File manager** to browse the existing files. Maintainer details are under **Settings → About phone**. This release has been tested through temporary boot. Flashing, formatting and OTA installation have separate effects on the installed system and require their own validation.

## Install recovery into boot

1. Temporarily boot the image with `fastboot boot skyward-nabu-boot.img`.
2. Wait for internal storage to open automatically so it is available for the backup.
3. Open **Install → Install Skyward to boot** and slide to confirm the bundled installer.
4. The installer verifies the device, unlocked bootloader, kernel and update state; backs up the complete current boot partition to `Skyward/boot-backups`; replaces its recovery ramdisk; writes the current slot and verifies the contents by reading them back.
5. Reboot to **System** for Android, or **Recovery** for Skyward.

The installed boot retains the existing kernel. The temporary image's forced-recovery arguments are removed from the installed header so the base init follows the bootloader's system/recovery choice. Install the recovery again after a ROM update replaces boot. To restore a backup, enter fastboot and flash the saved image to the same slot it was taken from (the backup filename begins with `boot_a` or `boot_b`).

The installer package is bundled in the recovery image and is also published as `skyward-nabu-boot-installer.zip` for installation from the matching Skyward recovery image.

## Report an issue

Include the ROM version, reproduction steps and relevant recovery logs. Review logs for personal information before sharing:

```bash
adb shell dmesg > dmesg.txt
adb logcat -d -b all > logcat.txt
adb pull /skyward/run recovery-run
```

## Credits and license

Device adaptation: **Seimo**. Recovery: **kirklin and Skyward contributors**. Base recovery, kernel and hardware components: the supplied ROM and their original authors. Adaptation source and patches: **GPL-3.0**; extracted components retain their original licenses. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
