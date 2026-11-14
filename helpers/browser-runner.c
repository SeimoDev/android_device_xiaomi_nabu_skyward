// SPDX-License-Identifier: GPL-3.0-or-later
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>

static void fail(const char *what) { perror(what); exit(2); }

static void bind_at(const char *root, const char *from, const char *to)
{
    char dst[4096];
    if (snprintf(dst, sizeof(dst), "%s%s", root, to) >= (int)sizeof(dst)) exit(2);
    if (mount(from, dst, NULL, MS_BIND, NULL)) fail(dst);
}

int main(int argc, char **argv)
{
    if (argc != 5 || getuid() != 0) {
        fprintf(stderr, "Usage (recovery root): %s ROOT DOWNLOADS WIDTH HEIGHT\n", argv[0]);
        return 2;
    }
    char *root = realpath(argv[1], NULL);
    if (!root) fail("realpath");
    if (unshare(CLONE_NEWNS)) fail("mount namespace");
    if (mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL)) fail("private mounts");
    bind_at(root, "/proc", "/proc");
    char proc[4096];
    snprintf(proc, sizeof(proc), "%s/proc", root);
    if (mount(NULL, proc, NULL, MS_BIND | MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL))
        fail("read-only proc");
    bind_at(root, "/dev/null", "/dev/null");
    bind_at(root, "/dev/urandom", "/dev/urandom");
    bind_at(root, "/dev/random", "/dev/random");
    bind_at(root, argv[2], "/downloads");
    if (chroot(root) || chdir("/")) fail("chroot");
    if (chown("/tmp/runtime", 65534, 3003) || chmod("/tmp/runtime", 0700))
        fail("runtime directory");
    struct rlimit core = {0,0};
    if (setrlimit(RLIMIT_CORE, &core)) fail("core limit");
    gid_t groups[] = {3003,1023,1015};
    if (setgroups(3, groups) || setgid(3003) || setuid(65534)) fail("drop privileges");
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) fail("no new privileges");
    clearenv();
    setenv("PATH", "/usr/bin:/bin", 1);
    setenv("HOME", "/tmp/home", 1);
    setenv("LANG", "C.UTF-8", 1);
    setenv("XDG_RUNTIME_DIR", "/tmp/runtime", 1);
    setenv("GIO_USE_PROXY_RESOLVER", "dummy", 1);
    setenv("GIO_USE_TLS", "gnutls", 1);
    setenv("WEBKIT_SKIA_ENABLE_CPU_RENDERING", "1", 1);
    setenv("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS", "1", 1);
    setenv("WEBKIT_DISABLE_MEMORY_PRESSURE_MONITOR", "1", 1);
    setenv("WPE_PLATFORM", "headless", 1);
    setenv("EGL_PLATFORM", "surfaceless", 1);
    setenv("LIBGL_ALWAYS_SOFTWARE", "1", 1);
    setenv("GALLIUM_DRIVER", "softpipe", 1);
    char *args[] = {"/opt/wpe/browser", argv[3], argv[4], NULL};
    execv(args[0], args);
    fail("browser");
}
