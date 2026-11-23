# Technical Feasibility Report

## Verdict
**Not currently feasible, and not assessable to completion, because `game_scarlett_master.exe` is not in the dump.** The executable contains the engine, gameplay, renderer, archive readers and platform glue; the files present are content archives, middleware DLLs and package metadata. A compatibility runtime has nothing to run. (HIGH)

If the executable is supplied intact, the *loading* part looks tractable and the *platform/graphics/data* parts look very hard; magnitude cannot be pinned down further without its import table and disassembly.

## 1. What can potentially be reused directly (HIGH unless noted)
| Item | Why |
|---|---|
| MSVC 14.29 runtime DLLs (10) | Standard redistributables, all imports resolve on Windows 10 |
| `libHttpClient.GDK.dll` | WinHTTP-based; all imports resolve |
| `XCurl.dll` | all imports resolve; lifecycle API (`RegisterAppStateChangeNotification`) and `xcurl_*` semantics untested |
| `amd_fidelityfx_loader_xbox.dll` | loads (no unresolved imports); only useful with its upscaler |
| Standard Win32/CRT/threading APIs used by all DLLs | host has them all |
| XAudio2 | present on Windows 10 (`XAudio2Create` = ordinal 1 verified) |

## 2. What needs translation (shim exports that forward/adapt)
| Item | Translation |
|---|---|
| `d3d12_xs!D3D12SerializeVersionedRootSignature`, `D3D12CreateRootSignatureDeserializer` | forward to host `d3d12.dll` (both exports verified present) — trivial |
| `xmem.dll` (4 functions) | map onto `VirtualAlloc`/aligned heap, decode attribute word; moderate (signature MEDIUM/LOW confidence) |
| Bink2 Scarlett → PC Bink 2 | needs RAD's PC binary (not in dump); API names match (MEDIUM) |
| Likely: GDK runtime calls from the exe (XUser, XStore, XGameSave, XTaskQueue, XPackage…) | unknown count; PC GDK has desktop implementations but entitlement/identity differs |

## 3. What needs reimplementation
| Item | Reason |
|---|---|
| Xbox DXR "rehydrate"/XDXR-stream BVH path (`XboxBvhBuilder`, `D3D12XBOX_*`) | No PC API ingests this; must rebuild BVHs from geometry via standard DXR or disable RT in the exe (needs code patching) |
| FSR 4 Scarlett upscaler binary | Scarlett-specific; replace by another upscaler integrated in the exe's render code |
| Xbox D3D12 device creation / memory-model extensions used by the exe | unknown scope; typically fixed-address GPU memory, console-specific resource creation, fast clears, etc. |
| Xbox Live / identity / entitlement layers | cannot be satisfied by local shims for online features |
| RPF/TTPF handling **if** the original code can't run | formats proprietary; would require reverse engineering and likely key handling — out of this project's declared rules |

## 4. What cannot currently be reproduced
- The game's code (absent).
- Console-integrity/entitlement checks and package encryption (not to be bypassed; out of scope).
- Any behaviour that depends on undocumented/NDA'd Xbox kernel features of GameOS; cannot be known without the exe.
- Shader/pipeline binaries if they are Scarlett GPU ISA (unknown; would be a hard stop for pure loader-based approach).

## 5. Biggest obstacles (ranked)
1. **Missing executable** — absolute blocker.
2. **Shader format / pipeline-state data** (`shaders.rpf`) — if hardware-specific, blocks any PC GPU rendering without source/IR.
3. **Xbox D3D12 extensions and unified-memory assumptions** — unknown scope; may require near-total backend emulation.
4. **Proprietary content containers with encrypted TOCs** — need the engine's own reader or full RE.
5. **GDK platform services** (identity, store, saves, Live) — shims feasible for offline play but nontrivial; online impossible without Microsoft services.
6. Scarlett-only binaries (FSR4, Bink Scarlett, BVH) — each needs a replacement.
7. Scale: ~208 GiB of data; any per-asset conversion pipeline is a project in itself.

## 6. Is a custom loader needed?
**Probably not (MEDIUM, conditional on the exe).** All 16 present PEs are conventional PE32+/AMD64; the Windows loader handles them if their unresolved imports (`xmem.dll`, `d3d12_xs.dll`, and any more the exe has) are satisfied by shim DLLs. A custom PE loader is only justified if the exe uses Xbox-only kernel/syscall behaviour, non-standard sections, or must be patched in memory. Since the exe is absent, none of this can be shown.

## 7. Is a game-specific runtime feasible?
In principle (single title, fixed code, fixed API set) a game-specific shim set is **more tractable than a general emulator**. Whether it is feasible for this title cannot be established now; the answer depends on the four unknowns in §5 (2)–(4). I would not commit to a build effort until Gate 0 and Gate 1 of the roadmap pass.

## 8. Difficulty assessment (given the exe is obtained)
Loader/shim stage: moderate. Graphics + shaders: very high (potentially prohibitive). Data/containers: high. Platform services: moderate–high. Overall: **very high; outcome uncertain.** Without the exe: **blocked.**

## 9. Items claimed compatible — with evidence
Only those in `dll-inventory.md` marked SUPPORTED_BY_WINDOWS, justified by successful host import resolution (static). No runtime compatibility was tested; none is claimed.
