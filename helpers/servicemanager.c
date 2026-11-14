/* Keep the recovery service directory on its generated framework manifest. */
#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <unistd.h>

int main(void) {
    if (unshare(CLONE_NEWNS) || mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL)) {
        perror("servicemanager mount namespace");
        return 1;
    }
    /* libvintf in this recovery predates the installed Android 17 schema.
     * Skyward publishes the needed services under /system/etc/vintf.
     * Hide installed manifests only from this process; other services still
     * read the full vendor configuration in init's mount namespace. */
    const char *paths[] = {
        "/vendor/etc/vintf", "/odm/etc/vintf",
        "/product/etc/vintf", "/system_ext/etc/vintf",
    };
    for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i) {
        struct stat st;
        if (stat(paths[i], &st)) {
            if (errno == ENOENT) continue;
            perror(paths[i]);
            return 1;
        }
        if (mount("tmpfs", paths[i], "tmpfs", MS_NOSUID | MS_NODEV, "mode=0755,size=65536")) {
            perror(paths[i]);
            return 1;
        }
    }
    execl("/system/bin/servicemanager", "/system/bin/servicemanager", (char *)NULL);
    perror("exec servicemanager");
    return 1;
}
