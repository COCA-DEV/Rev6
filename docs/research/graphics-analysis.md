# Graphics Analysis

Limits: the renderer lives in the missing exe. Everything here comes from three DLLs, the manifests and archive names.

## 1. API and runtime — Direct3D 12 on Scarlett (HIGH for "D3D12", MEDIUM for specifics)

| Evidence | Source |
|---|---|
| Imports from `d3d12_xs.dll` (Xbox Series D3D12 runtime; the `_xs` suffix = Xbox Series) | XboxBvhBuilder, amd_fidelityfx_upscaler_xbox import tables |
| Exports use `ID3D12Device11`, `ID3D12GraphicsCommandList4/6/8` and DXR types | XboxBvhBuilder export names |
| AMD loader PDB path `…\api\xbox\Gaming.Xbox.Scarlett.x64\Release\` → built with the Scarlett GDK platform | amd_fidelityfx_loader_xbox |
| Manifest `TargetDeviceFamily="Scarlett"` only | MicrosoftGame.Config |

No present image imports `dxgi.dll`, `d3d11.dll`, `d3dcompiler`, `dxcompiler`, or Vulkan/Metal. **DXGI**: no evidence either way (swap chain/present code would be in the exe; Xbox titles typically present through Xbox-specific present calls — not verified here). Direct3D 11 usage: UNKNOWN (not evidenced). Direct3D 12 on PC is *possible* (Windows 10 build 19045 here has `d3d12.dll`/`dxgi.dll`), but "D3D12 compatibility" of the **game** is not demonstrated: the title uses Xbox D3D12 extensions.

## 2. Xbox-specific graphics interfaces

1. **Xbox DXR extensions**: `D3D12XBOX_XDXR_STREAM_DESC`, `…_BATCHED_DESC2`, `Rehydrate*`, `Batched2X`, `Set64BitMortonCodes`, `CpuValidateResultX` (see `xbox-api-analysis.md` §3). Ray tracing is therefore used by the title (HIGH that the *builder* exists in the package; whether RT shipped enabled is UNKNOWN). PC DXR (`ID3D12Device5+`, `BuildRaytracingAccelerationStructure`) can substitute for build/copy/prebuild, **not** for `Rehydrate*`.
2. **GPU memory via XMem**: `XMemAlloc/XMemVirtualQuery` indicate GPU/CPU-shared memory management by attribute; PC splits system/VRAM memory — needs a heap/placement model.
3. **Upscaler**: `amd_fidelityfx_upscaler_xbox_fsr4_full_720p1080p_input_sanitize_scarlett_opt2` (name from PE export directory) — an AMD FSR 4 (ML) upscaler build, sized for 720p/1080p input, specialised for Scarlett ("opt2"). Binary contains Scarlett-targeted precompiled GPU code (MEDIUM; `.rdata` is 0x93EAE ≈ 606 KB, consistent with embedded weights/shaders, not examined). On PC the FSR 4 ML path is a different binary and requires specific AMD hardware; other GPUs would use other upscalers (DLSS/XeSS/FSR 3) which means reimplementing the integration inside the exe's render code, not just swapping a DLL.
4. **Video**: Bink 2 for Scarlett decodes with the GPU (`BinkRegisterGPUDataBuffers`, `BinkGetGPUDataBuffersInfo`, `BinkAllocateFrameBuffers`) — compute-based decode (MEDIUM: from API names only). The PC Bink GPU path would differ.

## 3. Shader formats — UNKNOWN
`shaders.rpf` (412 MB, encrypted/structured TOC) is the only shader container evidenced; it was not opened. Possible forms: DXIL (portable to PC via DXC/Agility runtime), DXBC, or **precompiled Scarlett (RDNA2) GPU binaries** (not portable; PC GPU needs source/IR). The Xbox GDK compiles HLSL to DXIL then to hardware code at build time for some titles; which one the game ships is not knowable from the dump. This is the single largest graphics-feasibility unknown, together with the pipeline-state cache location (possibly inside the same archive).

## 4. GPU resources, initialization, presentation — UNKNOWN
- Texture/mesh containers: `textures.rpf` (193 MB), `ttdb/*.ttpf` (≈64 GB, "RDS5" streamed packs) — formats proprietary, not decoded. Xbox textures are normally stored in GPU-swizzled tilings (Scarlett uses a console-specific tile layout); PC needs detiling/transcoding unless the engine stores a linear/BCn layout — UNKNOWN.
- Device creation, descriptor heap strategy, ExecuteIndirect use, mesh shaders, VRS, sampler feedback, DirectStorage/decompression-hardware use: no evidence.
- Presentation/HDR/frame pacing: no evidence.

## 5. Feasibility of a Windows graphics backend (HONEST)
- A D3D12 backend on PC is technically the closest match **in principle** (same API family), HIGH.
- Whether it is feasible for *this game* is **not decidable** without the exe: it depends on (a) which `D3D12XBOX_*` extensions the exe uses beyond BVH rehydrate (UNKNOWN), (b) shader format (UNKNOWN), (c) texture tiling (UNKNOWN), (d) memory-model assumptions (fixed GPU virtual addresses, direct GPU access to CPU memory) (UNKNOWN).
- Known hard blocks (HIGH): Xbox DXR rehydrate path and Scarlett-specific FSR 4 binary have no PC equivalent; both can be omitted only by modifying the exe's code paths, which a loader-only approach cannot do.
