# Skyward WPE 浏览器

首页的“浏览器”入口使用 WPE WebKit 2.54.2。地址栏支持 HTTP / HTTPS；网页支持触摸、滚动和原生软键盘输入。底部提供后退、前进、刷新、键盘和下载入口。文件保存到 `/sdcard/Download/Skyward`。浏览器读取 WLAN 高级设置中的代理及 DNS，重新打开后应用。

首次打开时，如果尚未安装组件，Skyward 会从 `SeimoDev/android_device_xiaomi_nabu_skyward` 最新 GitHub Release 自动下载 `skyward-browser-runtime.zip`，校验后安装并打开浏览器。请先连接 Wi-Fi 并解密内部存储；下载使用已配置的代理和 DNS。界面显示下载、校验、解包进度，支持取消及重试续传。也可手动卡刷组件包。

运行组件安装到 `/data/skyward/browser/root`，启动器随 Recovery 镜像提供。网页进程以 UID 65534 运行，使用独立挂载命名空间和根目录，仅将下载子目录绑定为可写存储。当前使用软件渲染，关闭媒体和 WebGL；WebKit 的 bubblewrap 沙箱未启用。关闭浏览器会结束它的进程组。

## 构建

在包含 `skyward/` 和 `.tools/` 的工作区中执行，或设置 `SKYWARD_WORKSPACE` 指向该工作区。

1. `sh browser/scripts/prepare-deps.sh` 准备 ARM64 Debian 依赖。
2. 在安装了 `gcc-aarch64-linux-gnu`、`pkg-config`、`meson`、`ninja-build`、`gcc`、`gettext`、`python3-packaging`、`patch` 的 Debian trixie 容器中，将 `.tools/wpe` 挂载到 `/work`，本目录挂载到 `/browser`。
3. 执行 `sh /browser/scripts/build.sh` 和 `sh /browser/scripts/build-glib.sh`。
4. 在工作区执行 `python3 browser/scripts/pack-runtime.py`，生成 `.tools/wpe/browser-runtime`。GLib 补丁适配部分 Android 内核的 pidfd / waitid 实现。
5. 执行 `python3 browser/scripts/package-addon.py .tools/wpe/browser-runtime out/browser/skyward-browser-runtime.zip` 打包安装组件。
6. 使用 Android NDK 编译 `src/android-runner.c`。设备的 `build.sh` 会自动编译同一份启动器。

`src/browser.c` 通过标准输入接收 JSON 命令，标准输出报告导航、输入焦点、下载和帧事件。网页 BGRA 帧原子写入 `output/view.bgra`，由 Skyward 转为 RGBA 并绘制。启动 WebKit 后再创建独立 JSC JSON 上下文，以使用正确的主线程事件循环。

网页引擎及依赖保留上游许可；运行包的 `usr/share/doc` 包含 Debian 版权文件。媒体、WebGL 和 HTTP Basic 登录对话框尚未接入此界面。

`dependencies.json` 记录本次构建使用的 Debian 包版本、摘要和对应源码地址。GLib 使用上游 2.90.1 源码及本目录中的 pidfd 补丁；桥接程序源码包含在此目录和 Release 的完整源码归档中。
