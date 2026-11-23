# DLL Inventory

Source: `tools/pescan.py` → `data/pe.json` (all imports/exports in full), `tools/resolve.py` (host resolution). SHA-256 in `data/sha256.txt`. "Present" = in the dump. All are PE32+ AMD64.

Classification (static evidence only; nothing was executed):
- `SUPPORTED_BY_WINDOWS` — every static import resolves on Windows 10 (or is bundled) and the module is a generic/portable component.
- `PARTIALLY_COMPATIBLE` — some imports resolve, some don't, or behaviour depends on a missing/Xbox module.
- `XBOX_SPECIFIC` — depends on Xbox-only modules/types and has no drop-in Windows equivalent.
- `UNKNOWN` — cannot be determined. `MISSING` — not in the dump.

## A. Game/middleware DLLs

| DLL | Present | Version / PDB evidence | Exports | Xbox-specific imports | Class | Windows equivalent | Conf. |
|---|---|---|---|---|---|---|---|
| **Bink2Scarlett.dll** (255,488 B) | yes | RAD Bink 2, PDB `C:\devel\projects\bink\build\Bink2Scarlett.pdb`, TS 2023-02-08 | 74 (`BinkOpen`, `BinkDoFrame`, `BinkDoFrameAsync*`, `BinkCopyToBuffer*`, `BinkOpenXAudio2`, `BinkFindXAudio2WinDevice`, `BinkRegisterGPUDataBuffers`, `BinkGetPlatformInfo`, `BinkSetSoundSystem[2]`, …, `RADTimerRead`) | `xmem.dll!XMemAlloc, XMemFree`; `XAudio2_9!ordinal 1 = XAudio2Create` (host-resolvable) | **PARTIALLY_COMPATIBLE** | RAD ships a PC Bink 2 build (`Bink2w64.dll`) with the same public API names — **not in dump**, not verified (MEDIUM) | HIGH (imports) / MEDIUM (equivalent) |
| **XboxBvhBuilder.dll** (884,224 B) | yes | TS 2026-03-27, has TLS | 12: C++ class `XboxBvhBuilder` — ctor(`ID3D12Device11*`, bool), `BuildRaytracingAccelerationStructure(ID3D12GraphicsCommandList4*, D3D12_BUILD_…_DESC*, UINT, POSTBUILD_INFO*)`, `BuildRaytracingAccelerationStructureBatched2X(ID3D12GraphicsCommandList6*, UINT, D3D12XBOX_…_BATCHED_DESC2*)`, `CopyRaytracingAccelerationStructure`, `CpuValidateResultX`, `GetRaytracingAccelerationStructurePrebuildInfo(…, D3D12XBOX_XDXR_STREAM_DESC*, …)`, `RehydrateRaytracingAccelerationStructure{X,BatchedX,Batched2X}` (CommandList8), `Set64BitMortonCodes`, `ValidateRehydrate…` | `xmem!XMemVirtualQuery`; `d3d12_xs!D3D12SerializeVersionedRootSignature` | **XBOX_SPECIFIC** | None. Standard DXR (D3D12) builds BVHs but cannot ingest `Rehydrate…`/`XDXR_STREAM` Xbox-format data | HIGH |
| **amd_fidelityfx_loader_xbox.dll** (13,312 B) | yes | AMD FidelityFX (Xbox) Loader 1.0.2.0; PDB `…\Gaming.Xbox.Scarlett.x64\Release\…` | 5: `ffxCreateContext, ffxDestroyContext, ffxConfigure, ffxQuery, ffxDispatch` | none (imports only libloader/CRT) | **PARTIALLY_COMPATIBLE** (loads the Xbox upscaler at run time — MEDIUM) | AMD's PC "ffx API" loader exists (`amd_fidelityfx_dx12.dll` family) with the same 5 entry points (MEDIUM) | HIGH/MEDIUM |
| **amd_fidelityfx_upscaler_xbox.dll** (786,432 B) | yes | AMD FidelityFX Upscaler 3.1.5.0; PE export name `amd_fidelityfx_upscaler_xbox_fsr4_full_720p1080p_input_sanitize_scarlett_opt2.dll` | 5 ffx entry points | `xmem!XMemAlloc, XMemFree, XMemGetWorkingSetStatistics`; `d3d12_xs!D3D12CreateRootSignatureDeserializer` | **XBOX_SPECIFIC** | FSR 3.x/4 PC upscalers exist as other AMD binaries; this one is a Scarlett-tuned FSR4 build and **cannot run on PC GPUs as is** (precompiled for Scarlett — MEDIUM) | HIGH/MEDIUM |
| **XCurl.dll** (199,152 B) | yes | "Microsoft Xbox XCurl 2604.5.0.0", Authenticode present | 61: libcurl API (`curl_easy_*`, `curl_multi_*`, `curl_url*`, `curl_mime*`, `curl_share*`) + `xcurl_global_init_mem/resume/set_request_limit/suspend` | none (WinHTTP, CRYPT32, ETW classic, `RegisterAppStateChangeNotification` — all host-resolvable) | **SUPPORTED_BY_WINDOWS** for loading; app-lifecycle + `xcurl_global_*` semantics UNTESTED | Microsoft's GDK XCurl (desktop build ships with the GDK — MEDIUM); or stock libcurl for the standard `curl_*` surface | HIGH |
| **libHttpClient.GDK.dll** (975,856 B) | yes | libHttpClient GDK 2.3.4, PDB `…\libHttpClient.GDK.pdb`, Authenticode | 129: `HC*` (HttpCall, WebSocket, Mock, Trace, Mem, Settings, `HCWinHttpSuspend/Resume`) | none (KERNEL32, ADVAPI32 ETW, WinHTTP, CRYPT32) | **SUPPORTED_BY_WINDOWS** | Open-source libHttpClient (Microsoft) is cross-platform; this build is the GDK flavour (uses WinHTTP) | HIGH |

## B. MSVC runtime set (chunk 1002; MSVC 14.29.30157.0, `amd64.onecore` builds, Authenticode-signed)

| DLL | Size | Exports | Class | Notes |
|---|---|---|---|---|
| vcruntime140.dll | 97,776 | 71 | SUPPORTED_BY_WINDOWS | imports API-set only |
| vcruntime140_1.dll | 37,848 | 3 | SUPPORTED_BY_WINDOWS | x64 /EHa frame handler |
| msvcp140.dll | 565,232 | 1,493 | SUPPORTED_BY_WINDOWS | |
| msvcp140_1.dll | 26,104 | 7 | SUPPORTED_BY_WINDOWS | |
| msvcp140_2.dll | 187,888 | 44 | SUPPORTED_BY_WINDOWS | |
| msvcp140_atomic_wait.dll | 57,312 | 32 | SUPPORTED_BY_WINDOWS | uses registry + threadpool API sets (host OK) |
| msvcp140_codecvt_ids.dll | 22,008 | 4 | SUPPORTED_BY_WINDOWS | |
| concrt140.dll | 298,992 | 291 | SUPPORTED_BY_WINDOWS | Concurrency Runtime |
| vccorlib140.dll | 336,888 | 256 | SUPPORTED_BY_WINDOWS | WinRT core library; imports `api-ms-win-core-winrt*`, host OK; listed because the engine may use C++/CX or WinRT activation — usage UNKNOWN |
| vcomp140.dll | 72,176 | 113 | SUPPORTED_BY_WINDOWS | OpenMP runtime, GUI subsystem build |

These are the standard Visual C++ redistributables (onecore flavour); the same DLLs can ship alongside any Windows exe (MEDIUM — licensing/redistributability of the dump copies is the owner's/Microsoft's matter; the equivalent official VC++ 14.29+ redistributable can be used instead).

## C. Referenced but NOT in the dump

| Module | Imported by | Class | Evidence |
|---|---|---|---|
| `xmem.dll` | Bink2Scarlett, XboxBvhBuilder, amd_fidelityfx_upscaler_xbox | **MISSING / XBOX_SPECIFIC** | import tables; absent from Windows System32 on this host and not in the dump |
| `d3d12_xs.dll` | XboxBvhBuilder, amd_fidelityfx_upscaler_xbox | **MISSING / XBOX_SPECIFIC** | same |
| `game_scarlett_master.exe` | (root) | **MISSING** | manifest/layout; see executable-analysis |
| Any further modules imported by the exe (e.g. GDK runtime DLLs, `dxgi`/presentation, input/network libs) | — | **UNKNOWN** | exe absent. No DLL in the dump imports `xgameruntime`, `dxgi`, `xinput`, `mmdevapi`, `ws2_32`, so none can be inferred from the present files |

## D. Non-DLL PE
`Catalog000.bin` — Xbox code catalog, not a library; see executable-analysis §5.

## E. Complete import-module list across all 16 DLLs
Windows host OK: ADVAPI32, KERNEL32, CRYPT32, OLEAUT32, WINHTTP, XAudio2_9; `api-ms-win-core-{com,console(l1,l2,l3),debug,errorhandling(l1-1-0..2),fibers,file(l1-1,l1-2,l2),handle,heap(l1,l2),interlocked,libraryloader(l1-2-0,1),localization(+obsolete),processenvironment,processthreads(l1-1-0,1),processtopology-obsolete,profile,psm-appnotify,registry(l1,l2),rtlsupport,string(+obsolete),synch(l1-1,l1-2-0,1),sysinfo(l1-1,l1-2),threadpool(l1-2,legacy),util,winrt,winrt-error,winrt-string}`, `api-ms-win-crt-{convert,environment,filesystem,heap,locale,math,runtime,stdio,string,time,utility}`, `api-ms-win-eventing-{classicprovider,provider}`. Bundled: MSVCP140, VCRUNTIME140, VCRUNTIME140_1. Not on Windows: xmem.dll, d3d12_xs.dll. Per-function lists: `data/pe.json`.
