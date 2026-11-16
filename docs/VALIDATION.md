# Release validation

The recovery base was tested on Xiaomi Pad 5 (nabu) running
`HyperOS_4.0.0.41_nabu_A17_by_zxcwsurx_20260920.zip`.

- Display, touch, root ADB, MTP session, Wi-Fi scanning, network connection and internet access: passed on the tablet.
- Existing files on unencrypted F2FS userdata: accessible from the recovery file manager.
- Maintainer card and boot installer entry: checked in light and dark UI rendering.
- Boot image: original ROM kernel retained byte-for-byte; gzip/CPIO contents, firmware inventory and AVB boot digest checked.
- Boot installer: persistent backup verification, device/kernel/capacity rejection, retained kernel, system boot arguments and boot AVB footer covered by tests.
- A complete installed image was prepared on the tablet from its existing boot partition; temporary boot of that image reached Android 17 with system startup complete.
- Recovery/image/installer/UI host tests and host/Android Clippy checks passed.
- The published patch applies to the pinned upstream commit, the bootstrap can run repeatedly on that checkout, and its reconstructed source passed the relevant host tests.

The bundled installer saved the original boot backup, wrote the current boot_a partition and verified its contents by reading it back on the tablet. Saved brightness and automatic unencrypted-data mounting were also confirmed after a fresh recovery start.
This original HyperOS 4 / Android 17 validation used unencrypted userdata.

## v0.3.1-nabu.2

The browser-enabled boot image was compiled and temporarily booted on the
tablet. The home-page entry launched the WPE bridge and exported live webpage
frames into Skyward. The preceding WPE prototype on the same recovery runtime
loaded HTTPS pages, received native touch and keyboard events, and downloaded
a file with its contents verified. This does not establish full website
compatibility for the integrated browser UI.

Advanced network work passed 47 skyward-net tests and 341 skyward-ui tests;
the initial browser integration passed 343 skyward-ui tests. Android builds
completed after the final browser viewport adjustment. The device repository's
reconstructed source was compared with the files used for the published image.

The browser runtime is a separate data-resident component. It uses software
rendering; media and WebGL are disabled. Its mount namespace, chroot and
unprivileged UID run with WebKit's bubblewrap sandbox disabled. This release's browser download UI has not been validated across other ROMs.

## v0.3.1-nabu.3

The on-device legacy ZIP installation was confirmed working with
`nabu_XiaomiPad5_OS3.0.303.0.WNXCNXM_16.0.zip` after the partition-release fix.
The recovery stages APEX payloads in RAM, keeps files needed by running
processes pinned, and retains a snapshot of the vendor/odm filesystem table.

The targeted skyward-block checks passed (39 tests), including retaining the
filesystem table after vendor disappears and preserving a complete RAM backing
image when a source read is short. Android release compilation and Clippy with
warnings denied completed successfully. The combined device patch reconstructs
the source used to build the release image.

## HyperOS 3 / Android 16 compatibility

The updated image was temporarily booted with
`nabu_XiaomiPad5_OS3.0.303.0.WNXCNXM_16.0.zip`. Firmware mounted successfully,
41 vendor runtime files were staged in RAM, the hardware Gatekeeper was selected,
and SharedSecret negotiation completed. The encrypted F2FS data partition opened;
after the user entered the existing screen-lock credential, no users remained
locked. The user confirmed access to the original internal-storage files and
working Wi-Fi on this packaged image.

The mount-option regression and nabu service-selection checks passed (40
skyward-block tests and 3 nabu fixture tests). Android release compilation and
Clippy with warnings denied also passed.

## Automatic browser component installation

The browser entry downloads a missing runtime from the latest device GitHub
Release and opens it after installation. Targeted checks passed for exact asset
selection and digest requirements, retaining an existing runtime on failure,
cancellation, and keeping the installation page active until the worker ends.
The published runtime ZIP was also unpacked successfully by the new installer.
Android release compilation and Clippy with warnings denied passed; the download
and error pages were rendered in both light and dark themes at nabu's panel size.
The combined patch reconstructs the sources used for the boot image.

On the tablet, the component downloaded and installed through the browser entry.
The installed chroot and public resources were corrected to be accessible by the
unprivileged browser, and the user confirmed the browser works. The updated image
includes installation-time normalization and startup repair of existing runtime
permissions. Targeted regression checks also passed with recovery's umask 077
and with a startup page archived with mode 000.

## Boot Control 1.1 slot discovery

The final image was temporarily booted on the tablet. Slot queries returned
current A, next active A, both slots bootable, A successful, B not yet marked
successful, and merge status None. The primary GPT header and entry checksums
also matched. Targeted tests covered both 512-byte and 4096-byte sectors, A and B
active flags, ambiguous flags and corrupted checksums. Android release compilation
and Clippy with warnings denied passed.
