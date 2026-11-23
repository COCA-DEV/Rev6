// Self-test for the shims. Loads ONLY the DLLs built by this project (next to this exe) and Windows' d3d12.dll.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>

static int g_fail = 0;
#define CHECK(c, ...) do { if (!(c)) { ++g_fail; printf("FAIL: " __VA_ARGS__); printf("\n"); } else { printf("ok:   " __VA_ARGS__); printf("\n"); } } while (0)

typedef LPVOID (WINAPI* PFN_XMemAlloc)(SIZE_T, ULONGLONG);
typedef VOID   (WINAPI* PFN_XMemFree)(PVOID, ULONGLONG);
typedef BOOL   (WINAPI* PFN_XMemVirtualQuery)(HANDLE, ULONG64, PVOID);
typedef BOOL   (WINAPI* PFN_XMemGetWS)(ULONG, PVOID);

static HMODULE load_local(const char* name)
{
    char dir[MAX_PATH];
    GetModuleFileNameA(nullptr, dir, MAX_PATH);
    char* slash = strrchr(dir, '\\');
    if (slash) *(slash + 1) = 0;
    char full[MAX_PATH];
    _snprintf_s(full, sizeof(full), _TRUNCATE, "%s%s", dir, name);
    return LoadLibraryA(full);
}

int main()
{
    HMODULE xm = load_local("xmem.dll");
    CHECK(xm != nullptr, "load xmem.dll (err=%lu)", GetLastError());
    if (xm) {
        auto alloc = (PFN_XMemAlloc)GetProcAddress(xm, "XMemAlloc");
        auto free_ = (PFN_XMemFree)GetProcAddress(xm, "XMemFree");
        auto vq    = (PFN_XMemVirtualQuery)GetProcAddress(xm, "XMemVirtualQuery");
        auto ws    = (PFN_XMemGetWS)GetProcAddress(xm, "XMemGetWorkingSetStatistics");
        CHECK(alloc && free_ && vq && ws, "all 4 xmem exports resolve");

        // Attribute constants observed in the real binaries.
        void* a = alloc(1000, 0x05E50000ULL);               // Bink: 32-byte alignment, no zeroing
        CHECK(a && ((uintptr_t)a % 32) == 0, "Bink attrs 0x05E50000 -> 32-byte aligned (%p)", a);
        free_(a, 0x05E50000ULL);

        void* b = alloc(4096, 0xA8004000ULL);               // upscaler: 256-byte alignment, zero-init
        bool zero = b != nullptr;
        for (int i = 0; b && i < 4096; ++i) if (((unsigned char*)b)[i]) zero = false;
        CHECK(b && ((uintptr_t)b % 256) == 0, "upscaler attrs 0xA8004000 -> 256-byte aligned (%p)", b);
        CHECK(zero, "upscaler attrs request zero-initialised memory");
        free_(b, 0xA8004000ULL);

        free_(nullptr, 0);                                  // must be a no-op
        CHECK(true, "XMemFree(NULL) is a no-op");

        char outbuf[0x40]; memset(outbuf, 0xCC, sizeof(outbuf));
        int stackvar = 0;
        BOOL r = vq(GetCurrentProcess(), (ULONG64)(uintptr_t)&stackvar, outbuf);
        CHECK(r == TRUE, "XMemVirtualQuery on committed stack memory -> TRUE");
        bool zeroed = true; for (char c : outbuf) if (c) zeroed = false;
        CHECK(zeroed, "XMemVirtualQuery out struct is zero-filled (layout unknown)");
        CHECK(vq(GetCurrentProcess(), 0x10, outbuf) == FALSE, "XMemVirtualQuery on invalid address -> FALSE");
        CHECK(ws(0x20000001, nullptr) == FALSE, "XMemGetWorkingSetStatistics -> FALSE (documented unsupported)");
    }

    HMODULE xs = load_local("d3d12_xs.dll");
    CHECK(xs != nullptr, "load d3d12_xs.dll (err=%lu)", GetLastError());
    HMODULE real = LoadLibraryA("d3d12.dll");
    CHECK(real != nullptr, "load system d3d12.dll");
    if (xs && real) {
        FARPROC f1 = GetProcAddress(xs, "D3D12SerializeVersionedRootSignature");
        FARPROC r1 = GetProcAddress(real, "D3D12SerializeVersionedRootSignature");
        CHECK(f1 && f1 == r1, "D3D12SerializeVersionedRootSignature forwards to d3d12.dll (%p == %p)", (void*)f1, (void*)r1);
        FARPROC f2 = GetProcAddress(xs, "D3D12CreateRootSignatureDeserializer");
        FARPROC r2 = GetProcAddress(real, "D3D12CreateRootSignatureDeserializer");
        CHECK(f2 && f2 == r2, "D3D12CreateRootSignatureDeserializer forwards to d3d12.dll (%p == %p)", (void*)f2, (void*)r2);
    }
    printf("\n%s (%d failure(s))\n", g_fail ? "SELFTEST FAILED" : "SELFTEST PASSED", g_fail);
    return g_fail ? 1 : 0;
}
