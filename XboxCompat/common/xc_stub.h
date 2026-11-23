// Traced stub for an Xbox-only function whose behaviour is not yet known.
//
// The signature is NOT known for these functions, so each stub accepts four register-sized arguments (the x64 Windows
// ABI passes the first four in RCX/RDX/R8/R9, so they can be logged without knowing the real prototype; extra or missing
// parameters only make the logged values meaningless, they cannot corrupt anything) and returns 0.
//
// Behaviour:
//   default                 log the call (XBOXCOMPAT_LOG) and return 0
//   XBOXCOMPAT_STRICT=1     log the call and terminate the process with exit code 0xC0DE0001, so the *first* unimplemented
//                           call is reported precisely instead of the game running on with a fabricated result.
// Returning 0 can mean S_OK / NULL / FALSE depending on the real function. That is why STRICT exists; do not rely on 0.
#pragma once
#include "xc_log.h"
#include <intrin.h>

namespace xc {

inline ULONG_PTR unimplemented(const char* module, const char* name,
                               ULONG_PTR a, ULONG_PTR b, ULONG_PTR c, ULONG_PTR d, void* retaddr)
{
    char where[300] = "?";
    HMODULE m = nullptr;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)retaddr, &m) && m) {
        char file[MAX_PATH] = "?";
        GetModuleFileNameA(m, file, MAX_PATH);
        const char* base = strrchr(file, '\\');
        _snprintf_s(where, sizeof(where), _TRUNCATE, "%s+0x%llx", base ? base + 1 : file,
                    (unsigned long long)((ULONG_PTR)retaddr - (ULONG_PTR)m));
    }
    log(module, "UNIMPLEMENTED %s(0x%llx, 0x%llx, 0x%llx, 0x%llx) called from %s",
        name, (unsigned long long)a, (unsigned long long)b, (unsigned long long)c, (unsigned long long)d, where);
    char strict[8];
    if (GetEnvironmentVariableA("XBOXCOMPAT_STRICT", strict, sizeof(strict)) && strict[0] == '1')
        TerminateProcess(GetCurrentProcess(), 0xC0DE0001);
    return 0;
}

} // namespace xc

#define XC_STUB(module, name) \
    extern "C" __declspec(dllexport) ULONG_PTR WINAPI name(ULONG_PTR a, ULONG_PTR b, ULONG_PTR c, ULONG_PTR d) \
    { return xc::unimplemented(module, #name, a, b, c, d, _ReturnAddress()); }
