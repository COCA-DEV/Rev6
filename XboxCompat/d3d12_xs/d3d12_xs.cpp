// d3d12_xs.dll shim.
//
// EVIDENCE: only two imports from d3d12_xs.dll appear in the present binaries (Addendum / xbox-api-analysis.md §2):
//   D3D12SerializeVersionedRootSignature      (XboxBvhBuilder.dll)
//   D3D12CreateRootSignatureDeserializer      (amd_fidelityfx_upscaler_xbox.dll)
// Both are public D3D12 APIs that the host d3d12.dll exports, so they are forwarded by the linker (see the linker pragmas below);
// no code runs for them.
//
// NOT PROVIDED, ON PURPOSE: Xbox-only device creation (D3D12XboxCreateDevice-family) and the D3D12XBOX_* extensions.
// No present binary imports them, their signatures are unknown, and inventing them would be fabrication. They must be
// added from the real game executable's import table (see implementation-roadmap.md, Gate 1).
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "xc_stub.h"

// Linker-level export forwarders: the loader resolves these directly inside d3d12.dll; no code of ours runs.
#pragma comment(linker, "/export:D3D12SerializeVersionedRootSignature=d3d12.D3D12SerializeVersionedRootSignature")
#pragma comment(linker, "/export:D3D12CreateRootSignatureDeserializer=d3d12.D3D12CreateRootSignatureDeserializer")

// D3D12XboxCreateDevice: HRESULT-returning (all D3D12 creation entry points are). Its parameter list was recalled from
// public Xbox documentation, NOT verified in the binary, so the pointers are not touched. Windows cannot create the Xbox
// device type, so the honest answer is E_NOTIMPL; the call is logged so the game's requested parameters can be inspected.
extern "C" __declspec(dllexport) HRESULT WINAPI D3D12XboxCreateDevice(ULONG_PTR a, ULONG_PTR b, ULONG_PTR c, ULONG_PTR d)
{
    xc::log("d3d12_xs", "D3D12XboxCreateDevice(0x%llx, 0x%llx, 0x%llx, 0x%llx) -> E_NOTIMPL (not available on Windows)",
            (unsigned long long)a, (unsigned long long)b, (unsigned long long)c, (unsigned long long)d);
    char strict[8];
    if (GetEnvironmentVariableA("XBOXCOMPAT_STRICT", strict, sizeof(strict)) && strict[0] == '1')
        TerminateProcess(GetCurrentProcess(), 0xC0DE0001);
    return (HRESULT)0x80004001L;   // E_NOTIMPL
}

// D3D12ConfigureVirtualMemoryX: console GPU virtual-memory policy. The exe calls it first, before any other Xbox call
// (trace: args = 3 pointers + 0). The signature is unknown; the GPU address space on Windows is owned by the driver/OS,
// so there is nothing to configure. Reported as success (S_OK) and logged with the raw arguments.
extern "C" __declspec(dllexport) HRESULT WINAPI D3D12ConfigureVirtualMemoryX(ULONG_PTR a, ULONG_PTR b, ULONG_PTR c, ULONG_PTR d)
{
    xc::log("d3d12_xs", "D3D12ConfigureVirtualMemoryX(0x%llx, 0x%llx, 0x%llx, 0x%llx) -> S_OK (no-op on Windows)",
            (unsigned long long)a, (unsigned long long)b, (unsigned long long)c, (unsigned long long)d);
    return S_OK;
}

// Exe imports without a known signature: traced stubs.
#include "../generated/d3d12_xs_missing.inc"

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID) { return TRUE; }
