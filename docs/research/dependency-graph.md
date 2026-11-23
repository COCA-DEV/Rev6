# Dependency Graph

Edges are static import-table entries from `data/pe.json` unless marked dashed (inferred). Dashed edges are MEDIUM/LOW.

```mermaid
graph TD
  EXE["game_scarlett_master.exe — MISSING"]:::missing
  EXE -.->|inferred: chunk 1002 content| BINK[Bink2Scarlett.dll]
  EXE -.-> BVH[XboxBvhBuilder.dll]
  EXE -.-> FFXL[amd_fidelityfx_loader_xbox.dll]
  EXE -.-> XCURL[XCurl.dll]
  EXE -.-> LHC[libHttpClient.GDK.dll]
  EXE -.-> CRT["MSVC 14.29 onecore set"]
  FFXL -.->|LoadLibraryExW at runtime, inferred| FFXU[amd_fidelityfx_upscaler_xbox.dll]

  BINK --> XMEM["xmem.dll — XBOX / MISSING"]:::xbox
  BVH --> XMEM
  FFXU --> XMEM
  BVH --> D3D12XS["d3d12_xs.dll — XBOX / MISSING"]:::xbox
  FFXU --> D3D12XS
  BINK --> XA29["XAudio2_9.dll (ord 1 = XAudio2Create) — host OK"]:::ok

  XCURL --> WINHTTP[WINHTTP.dll — host OK]:::ok
  XCURL --> CRYPT32[CRYPT32.dll — host OK]:::ok
  LHC --> WINHTTP
  LHC --> CRYPT32
  LHC --> ADV[ADVAPI32 / KERNEL32 — host OK]:::ok

  BINK --> VCR[VCRUNTIME140 / api-ms-win-crt-*]:::ok
  BVH --> MSVCP[MSVCP140 + VCRUNTIME140_1]:::ok
  FFXU --> MSVCP
  LHC --> MSVCP
  MSVCP --> VCR
  CONCRT[concrt140] --> MSVCP
  VCCOR[vccorlib140] --> WINRT["api-ms-win-core-winrt* — host OK"]:::ok
  classDef missing fill:#fdd,stroke:#c00;
  classDef xbox fill:#ffe9b3,stroke:#b80;
  classDef ok fill:#dfd,stroke:#080;
```

## Resolution matrix

| Edge target | Status | Consumers |
|---|---|---|
| Windows API sets / system DLLs | resolved on host (HIGH) | all 16 |
| CRT/STL set | bundled in dump | all C++ DLLs |
| `xmem.dll` | **unresolved** | Bink2Scarlett (XMemAlloc, XMemFree), XboxBvhBuilder (XMemVirtualQuery), upscaler (XMemAlloc, XMemFree, XMemGetWorkingSetStatistics) |
| `d3d12_xs.dll` | **unresolved** | XboxBvhBuilder (D3D12SerializeVersionedRootSignature), upscaler (D3D12CreateRootSignatureDeserializer) |
| main exe | **absent** | root of the graph |

## Plain-text topological order (load-order leaves first)
1. API sets, KERNEL32 → 2. VCRUNTIME140 → 3. VCRUNTIME140_1, MSVCP140 → 4. msvcp140_{1,2,atomic_wait,codecvt_ids}, concrt140, vcomp140, vccorlib140 → 5. XCurl, libHttpClient.GDK, FFX loader (all loadable on Windows) → 6. **[blocked: xmem.dll, d3d12_xs.dll]** → 7. Bink2Scarlett, XboxBvhBuilder, FFX upscaler → 8. game exe (missing).

## Not in the graph (UNKNOWN)
Anything the exe itself imports; any dynamically loaded modules (`LoadLibrary*` strings) — the exe is absent and no DLL string scan for dynamic loads was performed beyond import tables.
