// xmem.dll shim -- Xbox title-memory API implemented on the Windows CRT heap.
//
// EVIDENCE (docs/research/re-addendum-ghidra.md, Addendum 2):
//   XMemAlloc(size, attrs)          seen in Bink2Scarlett.dll (attrs 0x05E50000) and the FSR4 upscaler (0xA8004000)
//   XMemFree(ptr, attrs)            same attrs as the matching alloc
//   XMemVirtualQuery(proc, addr, out[0x40 bytes])   used by XboxBvhBuilder.dll to ask "is this GPU / CPU-readable memory?"
//   XMemGetWorkingSetStatistics(0x20000001 [, out]) telemetry only
//
// UNVERIFIED ASSUMPTION (MEDIUM confidence): the attribute word follows the Xbox 360 XALLOC_ATTRIBUTES bit layout:
//   bits 16..23 allocator id, bits 24..28 log2(alignment), bit 31 zero-initialise.
// Two independent checks in the decompiled callers agree (alignment 32 for Bink, 256 for the upscaler), but the
// real Xbox GDK header has not been seen. Every call is traced (XBOXCOMPAT_LOG) so attrs seen from the real game
// can be compared with this decoding.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <malloc.h>
#include <string.h>
#include "xc_stub.h"

namespace {
volatile LONG64 g_allocCount = 0;
volatile LONG64 g_freeCount = 0;
volatile LONG64 g_bytesLive = 0;

struct Hdr { SIZE_T size; };   // not used for layout; sizes tracked via _aligned_msize
}

static inline size_t decode_alignment(unsigned long long attrs)
{
    unsigned shift = (unsigned)((attrs >> 24) & 0x1F);
    size_t a = (size_t)1 << shift;
    return a < 16 ? 16 : a;    // x64 minimum, also required to be a power of two (it is)
}

extern "C" {

__declspec(dllexport) LPVOID WINAPI XMemAlloc(SIZE_T size, ULONGLONG attrs)
{
    const size_t align = decode_alignment(attrs);
    const bool zero = ((attrs >> 31) & 1) != 0;
    void* p = _aligned_malloc(size ? size : 1, align);
    if (p) {
        if (zero) memset(p, 0, size);
        InterlockedIncrement64(&g_allocCount);
        InterlockedAdd64(&g_bytesLive, (LONG64)size);
    }
    xc::log("xmem", "XMemAlloc(size=%zu, attrs=0x%llx) align=%zu zero=%d -> %p", (size_t)size, attrs, align, zero, p);
    return p;
}

__declspec(dllexport) VOID WINAPI XMemFree(PVOID p, ULONGLONG attrs)
{
    xc::log("xmem", "XMemFree(p=%p, attrs=0x%llx)", p, attrs);
    if (!p) return;
    InterlockedIncrement64(&g_freeCount);
    _aligned_free(p);
}

// Output layout (0x40 bytes = 8 qwords) is NOT known. The caller (XboxBvhBuilder) tests bits at +0x20 and +0x38 to
// decide whether an address is GPU memory. On Windows we cannot honestly claim GPU memory, so the structure is
// zero-filled and only the "address is valid committed memory" answer is reported.
__declspec(dllexport) BOOL WINAPI XMemVirtualQuery(HANDLE process, ULONG64 address, PVOID out)
{
    if (out) memset(out, 0, 0x40);
    MEMORY_BASIC_INFORMATION mbi;
    BOOL ok = FALSE;
    if (VirtualQueryEx(process, (LPCVOID)(ULONG_PTR)address, &mbi, sizeof(mbi)) && mbi.State == MEM_COMMIT)
        ok = TRUE;
    xc::log("xmem", "XMemVirtualQuery(proc=%p, addr=0x%llx, out=%p) -> %d (out layout unknown; zero-filled)",
            process, address, out, ok);
    return ok;
}

// First argument 0x20000001 is the only value observed; second argument is an output buffer of unknown layout.
// Returning FALSE is a valid "not available" answer: every observed caller treats it as optional telemetry.
__declspec(dllexport) BOOL WINAPI XMemGetWorkingSetStatistics(ULONG kind, PVOID out)
{
    xc::log("xmem", "XMemGetWorkingSetStatistics(kind=0x%lx, out=%p) -> FALSE (unsupported)", kind, out);
    (void)out;
    return FALSE;
}

// Exe imports not implemented yet (signatures/behaviour unknown): traced stubs. See tools/gen_stubs.py.
#include "../generated/xmem_missing.inc"

} // extern "C"

// Diagnostic only: when XBOXCOMPAT_LOG is set, log the first access violations (RIP as module+RVA, faulting address).
// It never handles the exception (returns CONTINUE_SEARCH), so game behaviour is unchanged.
static LONG CALLBACK xc_veh(PEXCEPTION_POINTERS ep)
{
    static volatile LONG count = 0;
    if (ep->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION && InterlockedIncrement(&count) <= 30) {
        const ULONG_PTR rip = (ULONG_PTR)ep->ExceptionRecord->ExceptionAddress;
        HMODULE m = nullptr; char file[MAX_PATH] = "?";
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)rip, &m) && m)
            GetModuleFileNameA(m, file, MAX_PATH);
        const char* base = strrchr(file, '\\');
        xc::log("xmem", "ACCESS VIOLATION rip=%s+0x%llx (abs 0x%llx) %s address=0x%llx",
                base ? base + 1 : file, (unsigned long long)(rip - (ULONG_PTR)m), (unsigned long long)rip,
                ep->ExceptionRecord->ExceptionInformation[0] == 0 ? "read" : ep->ExceptionRecord->ExceptionInformation[0] == 1 ? "write" : "execute",
                (unsigned long long)ep->ExceptionRecord->ExceptionInformation[1]);
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

BOOL APIENTRY DllMain(HMODULE, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        char tmp[8];
        if (GetEnvironmentVariableA("XBOXCOMPAT_LOG", tmp, sizeof(tmp)) || GetLastError() == ERROR_MORE_DATA)
            AddVectoredExceptionHandler(1, xc_veh);
    }
    return TRUE;
}
