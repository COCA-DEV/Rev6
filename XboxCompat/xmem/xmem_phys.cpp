// xmem.dll -- virtual-address windows and "physical page" pool.
//
// WHAT THE EXE DOES (evidence):
//   * trace of game_scarlett_master.exe (this project): XMemVirtualAlloc(NULL, 0x600000000, 0x20402000, 0x21, prot)
//     i.e. the first thing it does after D3D12ConfigureVirtualMemoryX is reserve a 24 GiB window.
//   * Leonida docs/xmem_exe_calls.md (third-party, GPL-3.0, read-only reference; its parameter order and the 64 KiB page
//     unit agree with our trace): XMemAllocatePhysicalPages / XMemMapPhysicalPages / XMemFreePhysicalPages /
//     XMemMapPhysicalPagesScatter have the shape of the Win32 AWE family, page unit 64 KiB.
//
// DESIGN (ours, not a copy of any third-party code): Windows AWE needs SeLockMemoryPrivilege, so the pool is emulated:
//   * "physical pages" are 64 KiB slices of pagefile-backed sections (256 MiB chunks created on demand);
//   * a MEM_PHYSICAL reservation becomes an address-space *placeholder* (VirtualAlloc2, Windows 10 1803+);
//   * mapping/unmapping a page replaces/restores the placeholder with a view of the slice (MapViewOfFile3).
//
// UNVERIFIED (kept honest -- every call is traced; unsupported combinations fail with a logged reason, never silently):
//   * meaning of the `attributes` argument and of `flags` in XMemAllocatePhysicalPages (logged only);
//   * allocation_type bits 0x4000 and 0x40000 (seen in the exe, meaning unknown) -> call is refused;
//   * the exact return type of XMemFreePhysicalPages (least certain); BOOL assumed;
//   * large-page behaviour (MEM_LARGE_PAGES 0x20000000) is ignored: ordinary 4 KiB pages are used.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <vector>
#include <unordered_set>
#include <map>
#include "xc_stub.h"

namespace {

constexpr ULONG_PTR kPage = 64 * 1024;
constexpr ULONG_PTR kChunkPages = 4096;                 // 256 MiB per section
constexpr ULONG kMemPhysical = 0x400000;
constexpr ULONG kMemLargePages = 0x20000000;

typedef PVOID (WINAPI* PFN_VirtualAlloc2)(HANDLE, PVOID, SIZE_T, ULONG, ULONG, MEM_EXTENDED_PARAMETER*, ULONG);
typedef PVOID (WINAPI* PFN_MapViewOfFile3)(HANDLE, HANDLE, PVOID, ULONG64, SIZE_T, ULONG, ULONG, MEM_EXTENDED_PARAMETER*, ULONG);
typedef BOOL  (WINAPI* PFN_UnmapViewOfFile2)(HANDLE, PVOID, ULONG);

PFN_VirtualAlloc2 pVirtualAlloc2;
PFN_MapViewOfFile3 pMapViewOfFile3;
PFN_UnmapViewOfFile2 pUnmapViewOfFile2;

SRWLOCK g_lock = SRWLOCK_INIT;
std::vector<HANDLE> g_chunks;                           // section handles
std::vector<bool> g_used;                               // page index -> allocated
std::map<ULONG_PTR, SIZE_T> g_windows;                  // reserved placeholder windows (base -> size)
std::unordered_set<ULONG_PTR> g_mapped;                 // page addresses currently holding a view

struct Guard { Guard() { AcquireSRWLockExclusive(&g_lock); } ~Guard() { ReleaseSRWLockExclusive(&g_lock); } };

bool load_apis()
{
    if (pVirtualAlloc2) return true;
    HMODULE k = GetModuleHandleW(L"kernelbase.dll");
    if (!k) return false;
    pVirtualAlloc2 = (PFN_VirtualAlloc2)GetProcAddress(k, "VirtualAlloc2");
    pMapViewOfFile3 = (PFN_MapViewOfFile3)GetProcAddress(k, "MapViewOfFile3");
    pUnmapViewOfFile2 = (PFN_UnmapViewOfFile2)GetProcAddress(k, "UnmapViewOfFile2");
    return pVirtualAlloc2 && pMapViewOfFile3 && pUnmapViewOfFile2;
}

bool in_window(ULONG_PTR a)
{
    auto it = g_windows.upper_bound(a);
    if (it == g_windows.begin()) return false;
    --it;
    return a >= it->first && a < it->first + it->second;
}

bool ensure_chunk(size_t chunk)
{
    while (g_chunks.size() <= chunk) {
        HANDLE h = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE,
                                      (DWORD)((kChunkPages * kPage) >> 32), (DWORD)(kChunkPages * kPage), nullptr);
        if (!h) { xc::log("xmem", "pool: CreateFileMapping failed err=%lu (commit limit?)", GetLastError()); return false; }
        g_chunks.push_back(h);
        g_used.resize(g_chunks.size() * kChunkPages, false);
    }
    return true;
}

bool unmap_page(ULONG_PTR va)
{
    if (!g_mapped.count(va)) return true;               // nothing mapped here: success (matches AWE semantics)
    if (!pUnmapViewOfFile2((HANDLE)-1, (PVOID)va, MEM_PRESERVE_PLACEHOLDER)) {
        xc::log("xmem", "pool: UnmapViewOfFile2(0x%llx) failed err=%lu", (unsigned long long)va, GetLastError());
        return false;
    }
    g_mapped.erase(va);
    return true;
}

bool map_page(ULONG_PTR va, ULONG_PTR pageIndex)
{
    if (va % kPage) { xc::log("xmem", "pool: map at unaligned 0x%llx", (unsigned long long)va); return false; }
    if (!in_window(va)) { xc::log("xmem", "pool: map outside any reserved window 0x%llx", (unsigned long long)va); return false; }
    if (pageIndex >= g_used.size() || !g_used[pageIndex]) {
        xc::log("xmem", "pool: map of unallocated page index %llu", (unsigned long long)pageIndex); return false;
    }
    if (!unmap_page(va)) return false;
    // Split a 64 KiB placeholder out of the window (no-op if already exactly that size), then replace it with a view.
    if (!VirtualFree((PVOID)va, kPage, MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
        DWORD e = GetLastError();
        if (e != ERROR_INVALID_PARAMETER) { xc::log("xmem", "pool: placeholder split at 0x%llx failed err=%lu", (unsigned long long)va, e); return false; }
    }
    HANDLE sec = g_chunks[pageIndex / kChunkPages];
    ULONG64 off = (ULONG64)(pageIndex % kChunkPages) * kPage;
    if (!pMapViewOfFile3(sec, (HANDLE)-1, (PVOID)va, off, kPage, MEM_REPLACE_PLACEHOLDER, PAGE_READWRITE, nullptr, 0)) {
        xc::log("xmem", "pool: MapViewOfFile3(0x%llx) failed err=%lu", (unsigned long long)va, GetLastError());
        return false;
    }
    g_mapped.insert(va);
    return true;
}

} // namespace

extern "C" {

// Parameter order per the exe's call sites: (address, size, allocation_type, attributes, protect).
__declspec(dllexport) LPVOID WINAPI XMemVirtualAlloc(LPVOID address, SIZE_T size, ULONG type, ULONG attrs, ULONG protect)
{
    LPVOID result = nullptr;
    const ULONG known = MEM_COMMIT | MEM_RESERVE | kMemPhysical | kMemLargePages;
    if (type & ~known) {
        xc::log("xmem", "XMemVirtualAlloc(addr=%p, size=0x%llx, type=0x%lx, attrs=0x%lx, prot=0x%lx) REFUSED: unknown type bits 0x%lx",
                address, (unsigned long long)size, type, attrs, protect, type & ~known);
        SetLastError(ERROR_NOT_SUPPORTED);
        return nullptr;
    }
    // Strip the graphics-only protection bits (0x800 0x1000 0x2000 0x8000 0x20000 0x40000); keep Win32 bits incl. WRITECOMBINE.
    ULONG win = protect & 0x7FF;
    if ((win & 0xFF) == 0) win = (win & ~0xFFu) | PAGE_NOACCESS;

    // MEM_PHYSICAL together with MEM_COMMIT = memory that is immediately usable (observed: the exe writes to it right
    // after the call, 20 MiB, type 0x20403000). Only a RESERVE-only MEM_PHYSICAL request is an address window that
    // XMemMapPhysicalPages later fills; that one becomes a placeholder.
    if ((type & kMemPhysical) && !(type & MEM_COMMIT)) {
        if (!load_apis()) { SetLastError(ERROR_NOT_SUPPORTED); return nullptr; }
        result = pVirtualAlloc2((HANDLE)-1, address, size, MEM_RESERVE | MEM_RESERVE_PLACEHOLDER, PAGE_NOACCESS, nullptr, 0);
        if (result) { Guard g; g_windows[(ULONG_PTR)result] = size; }
    } else {
        ULONG t = type & (MEM_COMMIT | MEM_RESERVE);
        result = VirtualAlloc(address, size, t ? t : MEM_RESERVE, (win & 0xFF) ? win : PAGE_READWRITE);
    }
    xc::log("xmem", "XMemVirtualAlloc(addr=%p, size=0x%llx, type=0x%lx, attrs=0x%lx, prot=0x%lx) -> %p (err=%lu)",
            address, (unsigned long long)size, type, attrs, protect, result, result ? 0 : GetLastError());
    return result;
}

// flags meaning unknown (0x180/0x280/0x380 observed). *pages: IN wanted count, OUT granted count (64 KiB pages).
__declspec(dllexport) BOOL WINAPI XMemAllocatePhysicalPages(ULONG_PTR flags, ULONG_PTR* pages, ULONG_PTR* pageArray)
{
    if (!pages || !pageArray) { SetLastError(ERROR_INVALID_PARAMETER); return FALSE; }
    Guard g;
    ULONG_PTR want = *pages, got = 0;
    for (ULONG_PTR idx = 0; got < want; ++idx) {
        if (idx >= g_used.size() && !ensure_chunk(idx / kChunkPages)) break;
        if (!g_used[idx]) { g_used[idx] = true; pageArray[got++] = idx; }
    }
    *pages = got;
    xc::log("xmem", "XMemAllocatePhysicalPages(flags=0x%llx, want=%llu) -> got %llu pages (%s)",
            (unsigned long long)flags, (unsigned long long)want, (unsigned long long)got, got == want ? "full" : "PARTIAL");
    return got != 0;
}

// pageArray == NULL: unmap `pages` pages starting at va.
__declspec(dllexport) BOOL WINAPI XMemMapPhysicalPages(PVOID va, ULONG_PTR pages, const ULONG_PTR* pageArray)
{
    if (!load_apis()) { SetLastError(ERROR_NOT_SUPPORTED); return FALSE; }
    Guard g;
    BOOL ok = TRUE;
    for (ULONG_PTR i = 0; i < pages && ok; ++i) {
        ULONG_PTR a = (ULONG_PTR)va + i * kPage;
        ok = pageArray ? map_page(a, pageArray[i]) : unmap_page(a);
    }
    xc::log("xmem", "XMemMapPhysicalPages(va=%p, pages=%llu, array=%p) -> %d%s", va, (unsigned long long)pages, pageArray, ok,
            pageArray ? "" : " [unmap]");
    return ok;
}

__declspec(dllexport) BOOL WINAPI XMemMapPhysicalPagesScatter(PVOID* vas, ULONG_PTR pages, const ULONG_PTR* pageArray)
{
    if (!vas || !load_apis()) { SetLastError(ERROR_INVALID_PARAMETER); return FALSE; }
    Guard g;
    BOOL ok = TRUE;
    for (ULONG_PTR i = 0; i < pages && ok; ++i)
        ok = pageArray ? map_page((ULONG_PTR)vas[i], pageArray[i]) : unmap_page((ULONG_PTR)vas[i]);
    xc::log("xmem", "XMemMapPhysicalPagesScatter(vas=%p, pages=%llu, array=%p) -> %d", (void*)vas, (unsigned long long)pages, pageArray, ok);
    return ok;
}

// Least certain signature (see header). Pages must have been unmapped by the caller.
__declspec(dllexport) BOOL WINAPI XMemFreePhysicalPages(ULONG_PTR pages, ULONG_PTR* pageArray)
{
    if (!pageArray) { SetLastError(ERROR_INVALID_PARAMETER); return FALSE; }
    Guard g;
    for (ULONG_PTR i = 0; i < pages; ++i)
        if (pageArray[i] < g_used.size()) g_used[pageArray[i]] = false;
    xc::log("xmem", "XMemFreePhysicalPages(pages=%llu, array=%p) -> TRUE", (unsigned long long)pages, pageArray);
    return TRUE;
}

} // extern "C"
