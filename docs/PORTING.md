# nabu platform adaptation

## Base and boot layout

Skyward is pinned to `c5e09f6eb644e75e051b309f98d6745ccbc97d81` (0.3.1).
The supplied HyperOS 4 / Android 17 port contains a complete TWRP-based recovery ramdisk in `boot.img`. The build reuses its init, Android runtime and kernel, replaces the recovery service with Skyward, and adds the dependencies listed in `materials.json`.

The 128 MiB image uses Android boot header v3, a gzip ramdisk and an unsigned AVB hash descriptor for `boot`. The temporary image carries `twrpfastboot=1` so the original first-stage init enters recovery despite the bootloader passing `androidboot.force_normal_boot=1`.

The bundled boot installer rebuilds the current slot's boot with its own kernel and header. It strips the temporary image's forced-recovery switches, inserts the Skyward ramdisk, adds an updated boot AVB footer, backs up the original partition and verifies the flash by reading it back. The kernel must match the build's reference kernel. The installer is included again in the installed ramdisk, supporting later reinstalls. Its payload stores the small files and archive metadata; large immutable system files are reconstructed from the running recovery only after each size and SHA-256 digest matches the build inventory.

## Display and input

The SM8150 display parameter identifies a display label. The patch resolves that label and the `qcom,dsi-panel` phandle to find the panel node. LCD brightness uses the WLED range. Eight original Novatek touch firmware files are copied into the recovery's own firmware directory so they remain accessible after vendor mounts.

The saved brightness is applied after the first display commit has completed, including an initial forced backlight synchronization.

## Android services

Linux 4.14 loop devices use `LOOP_SET_FD` and `LOOP_SET_STATUS64` when `LOOP_CONFIGURE` is unavailable. VNDK 30 is loaded from system_ext APEX. The base libbinder uses `SYST` interface-token headers. A servicemanager wrapper uses a private mount namespace to read the recovery-generated framework service declarations with its older libvintf.

The vendor uses Keymaster 4.1 and Gatekeeper 1.0. The compatibility launcher exposes the recovery base's Android Keystore compatibility service. Discovery selects the hardware Gatekeeper implementation when the framework also supplies gatekeeperd. AES-GCM requests pass purpose through KeyMint's operation argument; upgrade requests carry only the application binding. SharedSecret negotiation and screen-lock decryption work with the tested HyperOS 3 / Android 16 ROM.

## Wi-Fi

The kernel includes ICNSS and the WLAN host driver. The WLAN firmware runs in `msm/modem/wlan_pd`. QRTR, IPC router policy, PD Mapper, peripheral manager, remote storage, TFTP and CNSS are required before the interface appears. The overlay creates TFTP and WLAN directories and sets the wakelock permissions these services require. Firmware is mounted from the device's modem partition, and calibration data comes from its own persist partition. If the permissive recovery kernel rejects a vendor SELinux mount context with EINVAL, the mount is retried without the context options while retaining filesystem and access flags.

## Internal storage

The HyperOS 4 / Android 17 port uses plain F2FS userdata. Recovery automatically mounts it, checks the directory encryption policy and binds `/data/media/0` to `/sdcard`. The tested HyperOS 3 / Android 16 ROM uses metadata encryption and FBE with wrapped storage keys. Recovery opens the metadata layer and device-encrypted files; entering the existing screen-lock credential opens credential-encrypted internal storage.

## Maintainer information

`nabu.toml` declares Seimo as the device maintainer, with `https://github.com/SeimoDev` and `https://x.com/SeimoDev`. Skyward displays this card on the About page independently of upstream recovery attribution.

## Installer partition lifetime

APEX payloads used by the hardware services are staged under `/skyward/run/apex` in the recovery ramdisk before attaching their loop devices. This keeps the mounted VNDK and runtime independent of the logical partitions an installer must release. Installation pins files held by dynamically started processes as well as the configured services, and closes the browser process group before starting the installer.

The booted vendor/odm fstab is captured at `/skyward/run/fstab.snapshot`. Filesystem operations continue using that table after vendor is detached. The filesystem repair/format page currently enumerates data, metadata and cache; nabu has no standalone cache partition.

## Installed vendor runtime

The collector records vendor-specific fallback libraries and WLAN configuration in `vendor-runtime.files`. After mounting the installed vendor partition, recovery copies its matching files to RAM and binds them over the fallback paths before starting hardware services. Bionic, binder and VNDK libraries retain their existing loader paths. The RAM copies remain usable while an installer releases vendor.

## Browser component provisioning

The browser entry provisions a missing WPE runtime from the latest device GitHub Release. Asset selection requires the exact runtime filename, a valid upload SHA-256 and an HTTPS release URL. Downloaded partial files are named by digest so retries can resume the same component. Extraction reads only `runtime.tar.gz` into a fresh data directory, validates the ARM64 program, then publishes the directory with rollback. Installation progress and cancellation run on a worker while the recovery UI remains responsive.

Runtime resources are normalized for the unprivileged browser user: the chroot root is searchable, public resources are readable, and the ARM64 entry point is executable. Startup repairs permissions on previously installed resources while retaining private cache permissions. The ZIP packager also normalizes these resource modes.

## Boot Control 1.1

Boot control discovery accepts HIDL 1.1 as well as 1.2 and AIDL. With the Qualcomm 1.1 implementation, bootable/successful flags and slot switching use its HIDL methods. The next active slot is read from the boot partitions’ Qualcomm GPT attributes, with primary-header and partition-table CRC checks. This preserves the distinction between the booted slot and the next active slot.
