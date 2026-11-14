/* Host the recovery's Android Keymaster compatibility implementation. */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/system_properties.h>

int main(int argc, char **argv) {
    void *binder = dlopen("libbinder_ndk.so", RTLD_NOW | RTLD_GLOBAL);
    void *compat = dlopen("libkm_compat_service.so", RTLD_NOW | RTLD_LOCAL);
    if (!binder || !compat) {
        fprintf(stderr, "Keymaster compatibility libraries: %s\n", dlerror());
        return 1;
    }
    int32_t (*add)(void) = dlsym(compat, "addKeyMintDeviceService");
    void (*start)(void) = dlsym(binder, "ABinderProcess_startThreadPool");
    void (*join)(void) = dlsym(binder, "ABinderProcess_joinThreadPool");
    if (!add || !start || !join) {
        fprintf(stderr, "Keymaster compatibility entry points: %s\n", dlerror());
        return 1;
    }
    if (argc == 2 && strcmp(argv[1], "--check") == 0) {
        puts("Keymaster compatibility libraries loaded");
        return 0;
    }
    if (__system_property_set("skyward.keymaster.compat.ready", "") != 0) return 1;
    int32_t status = add();
    if (status != 0) {
        fprintf(stderr, "Register Keymaster compatibility service: %d\n", status);
        return 1;
    }
    start();
    if (__system_property_set("skyward.keymaster.compat.ready", "true") != 0) return 1;
    join();
    return 1;
}
