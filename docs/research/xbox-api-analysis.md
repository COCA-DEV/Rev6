# Xbox API Analysis

Scope: Xbox-specific APIs that are **imported or exported by the files present**. The game exe's own imports are unknown, so this list is necessarily partial — it must be extended once the exe is available. Calling convention for every x64 Windows/Xbox PE function is the single **Microsoft x64 ABI** (rcx, rdx, r8, r9, then stack; 32-byte shadow space) — HIGH, architectural. Signatures below were **not recovered from disassembly**; they come from public documentation recalled from memory (MEDIUM) and must be verified against call sites. Several signatures are UNKNOWN; they are marked so rather than guessed.

## 1. `xmem.dll` (Xbox memory management; not a Windows DLL — absent on host)

| API | Imported by | Signature | Behaviour | Windows equivalent | Complexity | Conf. |
|---|---|---|---|---|---|---|
| `XMemAlloc` | Bink2Scarlett, FFX upscaler | `LPVOID XMemAlloc(SIZE_T size, ULONGLONG attributes)` (MEDIUM; Xbox "XMem" documented in the XDK/GDK; 64-bit attribute word encodes alignment, memory type/pool, page size, allocator id) | Allocates from a categorised title-memory pool | `VirtualAlloc`/`_aligned_malloc`/`HeapAlloc`; attribute decoding must be reproduced for alignment/page-size/write-combine flags | LOW–MEDIUM for CPU memory; MEDIUM–HIGH if attributes request GPU-visible / write-combined memory | MEDIUM |
| `XMemFree` | Bink2Scarlett, FFX upscaler | `void XMemFree(PVOID p, ULONGLONG attributes)` (MEDIUM) | Frees XMemAlloc block; same attributes must be passed | `VirtualFree`/`_aligned_free` | LOW | MEDIUM |
| `XMemVirtualQuery` | XboxBvhBuilder | UNKNOWN (probably `VirtualQuery`-like) | Queries region info incl. memory attributes | `VirtualQuery` + side table | LOW–MEDIUM | LOW |
| `XMemGetWorkingSetStatistics` | FFX upscaler | UNKNOWN | Reports title working-set stats (name only) | `GetProcessMemoryInfo` (approx.) or stub | LOW | LOW |

Documented vs. undocumented: XMem is part of the Xbox platform SDK (restricted docs); nothing here can be verified publicly. Don't assume `XMemAlloc` ≈ `malloc`: the attributes argument is semantically load-bearing (alignment/pool/page size).

## 2. `d3d12_xs.dll` (Direct3D 12 runtime for Xbox Series "Scarlett")

| API | Imported by | Signature | Windows equivalent | Complexity | Conf. |
|---|---|---|---|---|---|
| `D3D12SerializeVersionedRootSignature` | XboxBvhBuilder | `HRESULT (const D3D12_VERSIONED_ROOT_SIGNATURE_DESC*, ID3DBlob** blob, ID3DBlob** error)` — public D3D12 API | **Identical export exists in host `d3d12.dll`** (verified) | trivial (forward) | HIGH |
| `D3D12CreateRootSignatureDeserializer` | FFX upscaler | `HRESULT (LPCVOID data, SIZE_T size, REFIID riid, void** ppDeserializer)` — public D3D12 API | **Exists in host `d3d12.dll`** (verified) | trivial (forward) | HIGH |

Real difficulty is not these two imports but what `d3d12_xs` objects return: `XboxBvhBuilder` is constructed with an `ID3D12Device11*` supplied by the (missing) game, i.e. the *exe* creates the device via an Xbox entry point (`D3D12XboxCreateDevice`-family, not imported by any present DLL and **not exported by host `d3d12.dll`** — verified). Anything calling `D3D12XBOX_*` types (see §3) has no PC counterpart.

## 3. Xbox D3D12 extension surface visible through `XboxBvhBuilder.dll` exports (HIGH — decorated C++ names)

Types named in exports: `ID3D12Device11`, `ID3D12GraphicsCommandList4/6/8`, `D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_DESC/INPUTS`, `D3D12_RAYTRACING_ACCELERATION_STRUCTURE_{PREBUILD_INFO,POSTBUILD_INFO_DESC,COPY_MODE}` (all standard PC DXR), and Xbox-only **`D3D12XBOX_XDXR_STREAM_DESC`**, **`D3D12XBOX_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_BATCHED_DESC2`**. Methods `BuildRaytracingAccelerationStructureBatched2X`, `RehydrateRaytracingAccelerationStructure{X,BatchedX,Batched2X}`, `CpuValidateResultX`, `Set64BitMortonCodes`. Interpretation (MEDIUM): Xbox DXR extension allowing prebuilt/serialised ("dehydrated") BVH data in a console-specific layout to be restored ("rehydrated") quickly; the `pack/*_bvh4/*.rpf` archives (e.g. `core_bvh4.rpf`, 8.3 GB) probably hold such data (LOW — names only). Windows DXR has no rehydrate path; a PC port must rebuild BVHs from geometry (loss of the precomputation benefit, large CPU/GPU cost).
Documented/undocumented: `D3D12XBOX_*` are part of the Xbox GDK (under platform licence); exact struct layouts were not recoverable.

## 4. XAudio2

| API | Imported by | Evidence | Windows | Conf. |
|---|---|---|---|---|
| `XAudio2_9.dll` ordinal 1 | Bink2Scarlett | ordinal 1 in host `XAudio2_9.dll` = `XAudio2Create` | Present on Windows 10 | HIGH |
| Bink exports `BinkOpenXAudio2`, `BinkFindXAudio2WinDevice`, `BinkSetSoundSystem2` | — | names | the "Win" naming suggests a Windows-device path exists in the same API | MEDIUM |

## 5. GDK service/runtime libraries (present)

| Library | API surface | Xbox-specific parts | Conf. |
|---|---|---|---|
| `libHttpClient.GDK.dll` 2.3.4 | `HCInitialize/HCCleanup(Async)`, `HCHttpCall*`, `HCWebSocket*`, `HCMock*`, `HCTrace*`, `HCMemSetFunctions`, `HCSetGlobalProxy`, `HCWinHttpSuspend/Resume` | uses only WinHTTP/CRYPT32; `HCWinHttpSuspend/Resume` are app-lifecycle hooks (PLM) | HIGH |
| `XCurl.dll` | libcurl 7.x-style API + `xcurl_global_{init_mem,resume,suspend,set_request_limit}` | the four `xcurl_*` functions are Xbox/GDK extensions (undocumented here; semantics inferred from names, LOW) | HIGH |
| Not found: `XGameRuntime`/`xgameruntime.dll`, `XUser*`, `XStore*`, `XPackage*`, `XGameSave*`, `XTaskQueue*`, `XGameUI*`, Xbox Live (`xsapi`) | — | **No evidence** in any present binary; their presence in the exe is likely (the title has TitleId, StoreId, microphone capability, protocol activation) but UNKNOWN | UNKNOWN |

`libHttpClient`'s presence implies Xbox services/HTTP use through the XSAPI-style stack (MEDIUM) — but it exports no Xbox Live symbols itself.

## 6. API summary table

| Category | Count of APIs evidenced | Hard to port? |
|---|---|---|
| XMem | 4 | moderate (semantics of attributes) |
| d3d12_xs public entry points | 2 | trivial |
| D3D12 Xbox extensions | ≥8 methods/types | very hard (no equivalent) |
| XAudio2 | 1 | trivial |
| XCurl extensions | 4 | low |
| GDK runtime/Live | 0 evidenced | unknown, likely large |
