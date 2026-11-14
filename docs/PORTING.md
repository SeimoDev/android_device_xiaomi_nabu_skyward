# nabu platform adaptation

## Base and boot layout

Skyward is pinned to `c5e09f6eb644e75e051b309f98d6745ccbc97d81` (0.3.1).
The supplied HyperOS 4 / Android 17 port contains a complete TWRP-based recovery ramdisk in `boot.img`. The build reuses its init, Android runtime and kernel, replaces the recovery service with Skyward, and adds the dependencies listed in `materials.json`.

The 128 MiB image uses Android boot header v3, a gzip ramdisk and an unsigned AVB hash descriptor for `boot`. The temporary image carries `twrpfastboot=1` so the original first-stage init enters recovery despite the bootloader passing `androidboot.force_normal_boot=1`.

The bundled boot installer rebuilds the current slot's boot with its own kernel and header. It strips the temporary image's forced-recovery switches, inserts the Skyward ramdisk, adds an updated boot AVB footer, backs up the original partition and verifies the flash by reading it back. The kernel must match the build's reference kernel. The installer is included again in the installed ramdisk, supporting later reinstalls. Its payload stores the small files and archive metadata; large immutable system files are reconstructed from the running recovery only after each size and SHA-256 digest matches the build inventory.

## Display and input

The SM8150 display parameter identifies a display label. The patch resolves that label and the `qcom,dsi-panel` phandle to find the panel node. LCD brightness uses the WLED range. Eight original Novatek touch firmware files are copied into the recovery's own firmware directory so they remain accessible after vendor mounts.

## Android services

Linux 4.14 loop devices use `LOOP_SET_FD` and `LOOP_SET_STATUS64` when `LOOP_CONFIGURE` is unavailable. VNDK 30 is loaded from system_ext APEX. The base libbinder uses `SYST` interface-token headers. A servicemanager wrapper uses a private mount namespace to read the recovery-generated framework service declarations with its older libvintf.

The vendor uses Keymaster 4.1 and Gatekeeper 1.0. The compatibility launcher exposes the recovery base's Android Keystore compatibility service. SharedSecret currently returns `-38`; credential decryption on encrypted ROMs remains unverified.

## Wi-Fi

The kernel includes ICNSS and the WLAN host driver. The WLAN firmware runs in `msm/modem/wlan_pd`. QRTR, IPC router policy, PD Mapper, peripheral manager, remote storage, TFTP and CNSS are required before the interface appears. The overlay creates TFTP and WLAN directories and sets the wakelock permissions these services require. Firmware is mounted from the device's modem partition, and calibration data comes from its own persist partition.

## Internal storage

The tested ROM disables both file and metadata encryption. The recovery mounts its plain F2FS userdata partition, checks the actual directory encryption policy and binds `/data/media/0` to `/sdcard`. Internal storage can then be browsed in the file manager.

## Maintainer information

`nabu.toml` declares Seimo as the device maintainer, with `https://github.com/SeimoDev` and `https://x.com/SeimoDev`. Skyward displays this card on the About page independently of upstream recovery attribution.
