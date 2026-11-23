# Addendum — Ghidra/REA static analysis of the present DLLs

Date: 2026-11-20. Tooling: REA `rea-agents` 6.10.1 CLI driving Ghidra 12.2 (JDK 25) at `D:\tools`. The MCP registration is not active in the session that ran this, so the CLI (`npx -y rea-agents@6.10.1 …`) was used. Analysis was done on **copies** in `D:\tools\work` (originals untouched). Nothing was executed. Evidence: REA Evidence IDs are inside the tool output; raw string extracts were produced with `rea search <dll> . --mode regex --kind strings --provider ghidra`.

Scope so far: `XboxBvhBuilder.dll`, `Bink2Scarlett.dll`, `amd_fidelityfx_upscaler_xbox.dll` (strings + header/byte-pattern level; no function-level decompilation yet). The first Ghidra import of `XboxBvhBuilder.dll` found 464 procedures, 454 defined strings, image base `0x180000000`, `.tdb` pseudo-segment from Ghidra.

## 1. Findings that update earlier documents

### 1.1 Engine identity — RAGE (HIGH, from embedded paths)
`XboxBvhBuilder.dll` contains build paths of the form `X:\americas\src\dev\rage\3rdparty\Microsoft\XboxBvhBuilder\Build\Release\Output\XboxBvhBuilder\<Shader>.pdb`. So Microsoft's XboxBvhBuilder is vendored under Rockstar's `rage` source tree (`rage` = Rockstar Advanced Game Engine; interpretation MEDIUM). This agrees with the `.rpf` archive family. It strongly suggests the game is a RAGE-derived engine; the `.rpf` readers are in the missing exe.

### 1.2 The `*_bvh4.rpf` archives and XDXR (MEDIUM-HIGH)
Strings: `XDXR_NODE_TYPE_TRI0..TRI3`, `BOX16`, `BOX32`, `INSTANCE`, `AABB_GEOMETRY`; `Header.version = 0x%x`, `Header.topLevelBVH = %d`; validation messages (`XdxrBoundingBox32 not contained by parent`, `Invalidated triangle (NAN) is reachable via BVH traversal`); shader names `PT_ConstructBVH4`, `ConstructBVH4`, `RefitBVH4`, `Box32Rehydration`, `Box16Rehydration`, `LeafRehydration`, `DecompressHeader`, `GetBVHCompactedSize`, `CopyAndCompactBVH`. And: `D3D12XBOX_RAYTRACING_ACCELERATION_STRUCTURE_POSTBUILD_INFO_OFFLINE_STATISTICS is only supported for offline BVH builds.`
Interpretation: the library is a **GPU compute implementation** of BVH4 construction (Morton codes, radix/bitonic sort, prefix sums, KDOP) plus **"rehydration"** (decompress a stored compact BVH into the runtime XDXR layout). XDXR = Xbox DXR native acceleration-structure format. The archives `core_bvh4.rpf` (8.3 GB), `story000_bvh4.rpf`, `shared_minigame000_bvh4.rpf` very likely hold pre-built compressed XDXR BVH data for rehydration (name correlation + library behaviour; still not verified by reading the archives).
Consequence: a PC port cannot consume these data directly (PC DXR acceleration-structure layout is opaque/vendor-specific); BVHs must be rebuilt from geometry via standard DXR, or the XDXR format reverse-engineered and re-encoded, which is vendor-opaque on PC.

### 1.3 Shaders embedded in the DLLs (partial answer for graphics-analysis §3)
Byte scan: `XboxBvhBuilder.dll` has 52 `DXBC` containers, 52 `RTS0` (root-signature parts) and 208 `DXIL` tag occurrences → these look like **DXIL compute shaders in DXBC containers with embedded root signatures**, i.e. the standard portable shader container. That makes the builder's own shaders potentially portable to PC D3D12 (shader model/intrinsic use not checked; Xbox-specific intrinsics would break this). `amd_fidelityfx_upscaler_xbox.dll`: 30 `DXBC`, 29 `RTS0`, **0 `DXIL`** occurrences — so its shaders are not plain DXIL-in-DXBC (legacy DXBC or a vendor-wrapped form; UNKNOWN). It also references a `'ACCC'` part and the strings `FFX_FSR4_XBOX_ACO`, `DeserializeComputePipelineStateX FAILED`, `XMemAlloc(%zu) FAILED`, `no usable 'ACCC' part … is this an ACO-cooked DLL? falling back to NewBE`. Interpretation (MEDIUM): the upscaler loads **precompiled GPU pipeline-state blobs via an Xbox-only API (`ID3D12…::DeserializeComputePipelineStateX`)** from "ACO-cooked" data, falling back to a "NewBE" path. Precompiled Scarlett pipeline states cannot run on PC GPUs. This confirms the earlier statement that the FSR 4 binary is Scarlett-specific.

### 1.4 New Xbox-only API names (add to `xbox-api-analysis.md`)
- `DeserializeComputePipelineStateX` (Xbox D3D12 extension; name only; signature UNKNOWN).
- `D3D12XBOX_RAYTRACING_ACCELERATION_STRUCTURE_POSTBUILD_INFO_OFFLINE_STATISTICS`, `D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BYTE_ALIGNMENT` (256-byte alignment of destination AS data — standard DXR rule).
- `pDevice->CreateRootSignature` and `D3D12SerializeVersionedRootSignature` used on the builder's own root signatures (standard).

### 1.5 FSR 4 configuration is fixed (MEDIUM)
Messages show the shipped upscaler supports only: fixed-resolution *Quality* models, HDR, **inverted depth**, auto-exposure, linear colour space, low-res motion vectors, jitter cancellation off; no dynamic resolution, no debug view, no sRGB/PQ postpass. This tells us how the game calls FSR 4 (inverted-depth, HDR, linear colour) — useful when choosing a PC upscaler replacement. The DLL also lists the whole FFX effect enum (FSR1/2/3/4, SPD, CACAO, SSSR, Brixelizer GI…) — only the upscaler is built in.

### 1.6 Bink (LOW new value)
`Bink2Scarlett.dll` strings: "BinkGPU is only supported for Bink 2.2 and later files", "Registered GPU buffers, while you have CPU buffers registered!" — confirms GPU-buffer decode API; no DXIL/DXBC inside (decode shaders are not embedded as DXBC; UNKNOWN where the GPU work happens).

## 2. Limits of this pass
- String/byte-level only; no decompilation of call sites yet (e.g. the exact `XMemAlloc` attribute argument values, calling convention check).
- `ACCC` count 32 in the upscaler may include code comparing the magic (one hit at file offset `0x480D` is `cmp …,'ACCC'` code), not 32 data parts.
- Ghidra memory-edit/checkpoint mode is disabled in this CLI mode: nothing persists between CLI invocations (each re-imports). For the future exe, enable `REA_GHIDRA_CHECKPOINT_DIR` (Linux/macOS only per REA docs) or use the MCP session.

## 3. Next static steps that don't need the exe
1. Decompile `XboxBvhBuilder::RehydrateRaytracingAccelerationStructureX` and `…GetPrebuildInfo` to recover the XDXR header layout (`Header.version`, `topLevelBVH`) — needed to ever re-encode `bvh4` data.
2. Decompile the `XMemAlloc` call sites in `Bink2Scarlett.dll`/upscaler to recover the real attribute constants → design `xmem.dll` shim.
3. Extract the embedded DXIL blobs from `XboxBvhBuilder.dll` and test with a DXIL validator for Xbox-only intrinsics.
4. Read the low-entropy-TOC `.rpf` headers.

---
# Addendum 2 — Decompiled call sites (function level)

Method: `rea decompile-all <copy.dll> --provider ghidra` for `Bink2Scarlett`, `XboxBvhBuilder`, `amd_fidelityfx_upscaler_xbox` (output kept outside the repo in `D:\tools\work\decomp_*`; Ghidra pseudocode, not original source). All findings below are from reading that pseudocode.

## A. `xmem.dll` — signatures recovered (upgrades `xbox-api-analysis.md` §1)

| API | Recovered usage | Conf. |
|---|---|---|
| `XMemAlloc(size, attrs)` | `Bink2Scarlett` `FUN_180025bf0`: `XMemAlloc(n + 0x40, 0x5e50000)`; returns pointer or 0 on failure. Upscaler `FUN_180004aa0`: `XMemAlloc(roundup256(n), 0xa8004000)`; logs "XMemAlloc(%zu) FAILED" when 0. Two args; second is a 32-bit-looking constant | HIGH (call shape) |
| `XMemFree(ptr, attrs)` | Bink `FUN_180025bc0`: `XMemFree(base, 0x5e50000)` — **same attrs as the alloc**; upscaler: `XMemFree(p, 0xa8004000)` | HIGH |
| `XMemVirtualQuery(HANDLE proc, ULONG64 addr, OUT struct*)` | `XboxBvhBuilder` `FUN_180019bb0`: `XMemVirtualQuery(GetCurrentProcess(), addr, &info)`; `info` is cleared as 8 qwords (0x40 bytes); returns nonzero on success; the caller then tests `info+0x38 & 3`, `info+0x20 & 0x1000` and `info+0x20 & 0x600000000` to decide whether an address is **GPU memory** ("DestAccelerationStructureData must point to GPU memory") or **CPU-readable memory** | HIGH shape / LOW field meaning |
| `XMemGetWorkingSetStatistics(0x20000001 [, struct*])` | upscaler: first arg constant `0x20000001`; second arg an output buffer (`local_cf8`, `local_d8`, `local_a8`); returns nonzero on success; only used for memory logging/telemetry | MEDIUM |

**Attribute word (hypothesis, MEDIUM).** The two constants fit the Xbox 360-style `XALLOC_ATTRIBUTES` bit layout I recall (not verified against GDK headers): bits 24–28 = log2(alignment), bits 16–23 = allocator id, bit 31 = zero-initialise, bits 29–30 = protection, bit 14 = must-succeed. Check: Bink `0x05E50000` → alignment code 5 = 32 B, and Bink's own wrapper aligns blocks to 32 (`0x40 - (p & 0x1f)`, storing the offset in the byte before the block) ✔; upscaler `0xA8004000` → alignment code 8 = 256 B, and the caller rounds sizes to 256 (`+0xff & ~0xff`) ✔. Both independent checks agree. Practical shim rule until the GDK header is available: `alignment = 1 << ((attrs >> 24) & 0x1f)`, honour bit 31 (zero-fill), keep the same attrs for free, otherwise use `_aligned_malloc/VirtualAlloc`.

Bink also supports a caller-provided allocator (`BinkSetMemory`): `DAT_18003efa8` is tried first and `XMemAlloc` is the fallback; blocks from the custom allocator are tagged `3` in `ptr[-2]`.

## B. `XboxBvh4Header` — the XDXR BVH4 header (HIGH for field names, MEDIUM for offsets)
Function `FUN_180002df0` (a debug dump in `XboxBvhBuilder.dll`, takes `XboxBvh4Header const*`) prints, in order, these members (dword index → byte offset):

| dword | offset | member | note |
|---|---|---|---|
| 0 | 0x00 | `version` (low 16 bits) + `flags` (whole dword); `topLevelBVH` = !(bit 31) | bit 31 clear ⇒ top-level BVH |
| 1 | 0x04 | `totalSizeIn64BNodes` | size in 64-byte nodes |
| 2 | 0x08 | `crc32` | integrity of the structure |
| 3 | 0x0C | `numElements` | |
| 4–9 | 0x10–0x27 | `sceneBounds` (6 floats) | printed as X(a;b) Y Z with a=dword4, b=dword7 ⇒ min xyz = dwords 4–6, max xyz = 7–9 (MEDIUM) |
| 12 | 0x30 | `rootNodePtr` | |
| 13 | 0x34 | `offsetToElements` | |
| 14 | 0x38 | `offsetToParents` | parent array exists |
| 15 | 0x3C | `objectToLocalScale` | three packed bytes turned into floats by `<<0x17` (exponent-only floats) |

Node types: `XDXR_NODE_TYPE_TRI0..3`, `BOX16`, `BOX32`, `INSTANCE`, `AABB_GEOMETRY`; leaf/box rehydration shaders exist (`Box32Rehydration`, `Box16Rehydration`, `LeafRehydration`, `DecompressHeader`). Public `Rehydrate…X` methods are thin forwarders (`0x1800219f0 → FUN_180015c60`); real work happens in GPU compute shaders.
Implication: the structure is documented enough to write a **reader/validator** for BVH data (dword 0 version/flags, size, crc32) and to inspect `*_bvh4.rpf` payloads once they can be read — but it cannot be fed to PC DXR; PC would need a rebuild from geometry.

## C. Embedded validations that document D3D12XBOX usage
Strings with source line numbers (`FUN_180019290(param_1, 0x483, …)`): "pDesc->SourceAccelerationStructureData must be non-null and point to CPU-readable memory", "DestAccelerationStructureData must point to GPU memory". So `Rehydrate` takes a **CPU-readable source BVH blob** and writes a **GPU-resident acceleration structure**: i.e. the stored BVH is loaded by CPU (from the archive) and expanded on GPU.

## D. Still open
1. `DeserializeComputePipelineStateX` call: vtable slot `+0x218` on the device object in `FUN_180004aa0` (argument block holds blob pointer/size, a GUID at `DAT_180048330`) — Xbox `ID3D12Device` extension; layout not reverse-engineered.
2. Exact meaning of `XMemVirtualQuery` result bits.
3. Everything involving `XMemAlloc` in the missing exe (attributes will differ per use).
