# XboxCompat — Research Overview

Phase: research only. No runtime was written. No binary from the dump was executed or loaded.
Analysis date: 2026-11-20. Dump root: `D:\xbox series dump\GTA6.Xbox.v1.0.2.1` (read-only inspection; no original file was modified — all new files live under `docs/research/`).

Confidence scale used in every document: **HIGH** = read directly from bytes/manifests or verified on the host; **MEDIUM** = strong inference or recalled public documentation not verified in the binary; **LOW** = hypothesis; **UNKNOWN** = no evidence.

## Headline findings

1. **The game executable is not in the dump.** `MicrosoftGame.Config`, `appxmanifest.xml` and the GDK layout file all name `game_scarlett_master.exe` (Id `GTAO`, `TargetDeviceFamily="Scarlett"`). The layout lists 104 files; 103 exist on disk, and the single missing one is `game_scarlett_master.exe` (layout chunk `1001`). No file with that name, and no other game-sized executable, exists anywhere in the dump. (HIGH)
2. Everything that *is* present is either **(a)** Rockstar content archives (`.rpf`, `.ttpf`: ~208 GiB, formats proprietary, TOCs mostly high-entropy), **(b)** 16 standard PE32+ x86-64 DLLs (middleware + MSVC runtime), **(c)** package metadata, **(d)** two files *not* in the layout: `gameos.xvd` (an XVD container) and `Catalog000.bin` (an Xbox code-catalog pseudo-PE). (HIGH)
3. The 16 DLLs are **ordinary PE32+/AMD64 images** that a stock Windows loader can parse. Three Xbox-only import DLLs are absent on Windows — `xmem.dll` (3 importers) and `d3d12_xs.dll` (2 importers) — so those three DLLs (Bink2Scarlett, XboxBvhBuilder, amd_fidelityfx_upscaler_xbox) fail to load on stock Windows until shims exist. Every other import of every DLL (all remaining system/API-set DLLs, 100% of named imports) resolves on this Windows 10 host. (HIGH — verified by `LoadLibraryEx`/`GetProcAddress` of host system DLLs only.)
4. Graphics evidence points to **Direct3D 12 on the Scarlett runtime (`d3d12_xs`)**, with Xbox-extension ray-tracing BVH code (`XboxBvhBuilder.dll`, `D3D12XBOX_*` types) and an AMD FSR 4 build specific to Scarlett. No DXGI import appears in any present DLL. (HIGH for D3D12/Xbox extensions; presentation path UNKNOWN because it lives in the missing exe.)
5. **Verdict: XboxCompat cannot be built or even validated for this game today.** The game's code (all gameplay, engine, RPF/TTPF readers, shader loading, platform glue) is in the missing executable. Without it the central questions (full import set, Xbox API surface, shader format, RPF key handling) are unanswerable. See `feasibility-report.md`.

## Document map

| File | Content |
|---|---|
| `dump-structure.md` | Complete file inventory, signatures, package layout, container formats |
| `executable-analysis.md` | Missing exe proof, PE analysis of 16 images, `Catalog000.bin`, `gameos.xvd`, loader feasibility |
| `dll-inventory.md` | Per-DLL table (format, exports, imports, classification) |
| `dependency-graph.md` | Module/import graph, resolved vs. unresolved edges |
| `xbox-api-analysis.md` | Every Xbox-specific API found, with signature confidence |
| `graphics-analysis.md` | D3D12/Scarlett evidence, ray tracing, upscaler, shaders |
| `subsystem-analysis.md` | Audio, input, network, filesystem, memory, threads, identity |
| `feasibility-report.md` | Honest assessment, obstacles, reuse/translate/reimplement |
| `implementation-roadmap.md` | Gated plan (Gate 0 = obtain the executable) |

Reproduction aids: `tools/pescan.py`, `tools/resolve.py`, `tools/containers.py`, `tools/layoutcheck.py`; raw output `data/pe.json`, `data/sha256.txt`. Run Python with `-I`.

## What was deliberately NOT done

- No Ghidra/disassembly: Ghidra is not installed, and the only valuable target (the main exe) does not exist. The DLLs were analysed at the PE-metadata level (headers, imports, exports); their code was not disassembled.
- No decryption of `gameos.xvd`, `.rpf`, or `.ttpf` content and no key extraction (out of scope per rules: no DRM/platform-security bypass).
- No DLL was loaded from the dump (loading runs `DllMain`). Host system DLLs were loaded only to test whether import names resolve.
- No claim about the game's authenticity beyond what the package metadata states (title "Grand Theft Auto VI", `RockstarGamesInc.28872443D20A7`, version 1.0.2.1, TitleId `7952987A`).
