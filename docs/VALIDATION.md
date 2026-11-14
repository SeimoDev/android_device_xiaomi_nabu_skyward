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

Permanent boot partition writes have not been exercised on the tablet.
Credential-based FBE decryption remains unverified because the tested ROM disables encryption.
