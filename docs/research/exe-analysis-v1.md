# game_scarlett_master.exe — first analysis (exe now available)

Date: 2026-11-23. File: `D:\xbox series dump\GTA6.Xbox.v1.0.2.1\game_scarlett_master.exe`, 120,181,760 bytes, SHA-256 `e95020b2fa4a721db3df59fdecf75621730ac559d8835252f6c3b658d5a08993`. Analysis done on a copy (`D:\tools\work\exe`); the file was only read, never executed. Provenance: supplied by the owner after it was found at another path; it was not in the original dump, and its authenticity relative to the console install is not independently verified.

## 1. Format (HIGH — `tools/pescan.py`, `docs/research/data/exe_pe.json`)
- PE32+ (magic 0x20B), AMD64, GUI subsystem (2), OS version 6.0, linker 14.0, ImageBase `0x140000000`, SizeOfImage `0x0B06D000`.
- Entry RVA `0x056A1EC8`; TLS directory present (RVA `0x6771DD0`); load-config, exception (`.pdata` 0x36CBAC bytes) and base-relocation tables present; DllCharacteristics `0x8160` (ASLR, high-entropy VA, NX, CFG-aware).
- Sections: `.text` 0x5F3F966, `.rdata`, `.data` 0x43EC398 (large), `.pdata`, `.retplne`, `.tls`, `.voltbl`, **`.xbld` (twice)**, `.reloc`. Same Xbox toolchain marker `.xbld` as the DLLs.
- Header timestamp 2026-11-13T21:40:36 (a real date, unlike the reproducible-build DLLs).
- PDB path: `X:/americas/src/sub_story/game/vs_project/Gaming.Xbox.Scarlett.x64/Build/master/game_scarlett_master.pdb` → "master" (retail) configuration of the **Scarlett x64** GDK platform; confirms the project tree layout seen in the BVH builder strings (`x:\americas\src\dev\rage\…`).
- One export (the module name only).
- Answer to "can a conventional Windows loader load it?": the PE is conventional, but 6 import DLLs do not exist on Windows (§2). With shims placed beside the exe, the stock loader can in principle bind it (MEDIUM; not attempted — nothing was executed).

## 2. Imports (HIGH — import table)
Imports **no** `dxgi`, `d3d11`, `xgameruntime` or `xaudio2`. All Windows-side imports (api-ms-win-*, ext-ms-win-rtcore-ntuser-*, WS2_32 with 25 functions, WINHTTP 15, MFPlat 6, MFReadWrite 1, bcrypt 3, MSVCP140 113, VCRUNTIME140, ADVAPI32 3, GameInput.dll ordinal 1) resolve on this Windows 10 host except as listed below. GDK services (XGameRuntime) are therefore either loaded dynamically or reached through `libHttpClient.GDK.dll` only — UNKNOWN until string/`LoadLibrary` analysis.

### 2.1 Imports from dump-bundled DLLs
`XboxBvhBuilder.dll` 7 (`XboxBvhBuilder` ctor/dtor, `GetRaytracingAccelerationStructurePrebuildInfo`, `CopyRaytracingAccelerationStructure`, `BuildRaytracingAccelerationStructureBatched2X`, `RehydrateRaytracingAccelerationStructureBatched2X`, `Set64BitMortonCodes`), `Bink2Scarlett.dll` 23 (open/doframe/async/subtitle-less playback + `BinkSetMemory`, `BinkSetOSFileCallbacks`, `BinkRegisterFrameBuffers`, `BinkGetFrameBuffersInfo`), `amd_fidelityfx_loader_xbox.dll` 4, `libHttpClient.GDK.dll` 38. Windows-only equivalents needed for Bink; the BVH path uses only the `Batched2X` rehydrate variants.

### 2.2 Xbox-only imports (NEW information — all absent on Windows)
| DLL | Functions | Role (inference) | Covered by XboxCompat today |
|---|---|---|---|
| `xmem.dll` (12) | `XMemAlloc` ✔, `XMemFree` ✔, `XMemGetWorkingSetStatistics` ✔, **`XMemAllocDefault`, `XMemFreeDefault`, `XMemAllocatePhysicalPages`, `XMemFreePhysicalPages`, `XMemMapPhysicalPages`, `XMemMapPhysicalPagesScatter`, `XMemTransferMemory`, `XMemVirtualAlloc`, `XMemIsToolsMemAvailable`** | physical-page / GPU-visible memory management | 3 of 12 |
| `d3d12_xs.dll` (3) | `D3D12SerializeVersionedRootSignature` ✔, **`D3D12XboxCreateDevice`**, **`D3D12ConfigureVirtualMemoryX`** | device creation + GPU VM configuration (Xbox-only) | 1 of 3 |
| `xg_xs.dll` (2) | `XGCreateTextureComputer`, `XGSuggestSwizzleMode` | Xbox texture addressing/swizzle library (XG) | 0 |
| `chad.dll` (5) | `XDspActivate`, `XDspConnectWithMaximumStreamLimit`, `XDspDeactivate`, `XDspDisconnect`, `XDspSubmitCommand` | Scarlett audio DSP command interface | 0 |
| `xapu.dll` (5) | `XApuConnect`, `XApuDequeueResult`, `XApuDisconnect`, `XApuEnqueueCommand`, `XApuGetResultCount` | audio processing unit (APU) command queue | 0 |
| `AcpHal.dll` (9) | `AcpHalCreate`, `AcpHalAllocateShapeContexts`, `AcpHalReleaseShapeContexts`, `ApuAlloc`, `ApuCreateHeap`, `ApuFree`, `ApuIsVirtualAddressValid`, `ApuMapApuAddress`, `ApuMapVirtualAddress` | audio co-processor HAL, APU memory | 0 |
| `XCRDAPI.dll` (1) | `DStorageGetFactory` | Xbox DirectStorage (hardware decompression of game data) | 0 |

Signatures for all uncovered functions are UNKNOWN (to be recovered from call sites). `DStorageGetFactory` matches the public DirectStorage factory entry point name; Windows has DirectStorage (`dstorage.dll`) with a different, PC-oriented implementation.

## 3. What this changes
1. Gate 0 (get the exe) is **passed**.
2. The exe does **not** link DXGI: presentation goes through Xbox-only paths (`D3D12XboxCreateDevice`). A PC backend needs a device/swap-chain creation layer, not just forwarders.
3. Three Xbox-hardware audio stacks (`chad`, `xapu`, `AcpHal`) are used directly; they are NOT XAudio2. Audio will need a software replacement of what these command interfaces do (unknown until call sites are read).
4. Hardware-assisted asset decompression (`DStorageGetFactory` via `XCRDAPI`) — relevant to how `.rpf`/`.ttpf` payloads are read.
5. Texture layout: `XGSuggestSwizzleMode` / `XGCreateTextureComputer` → textures are in console swizzle formats; PC needs detiling (this answers the earlier open question in `graphics-analysis.md` §4: swizzle IS involved, MEDIUM-HIGH).
6. Next: recover signatures at call sites in Ghidra (in progress), then extend `XboxCompat` with traced stubs and real implementations only where evidence allows.
