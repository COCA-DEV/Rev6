# Implementation Roadmap (gated)

Nothing below is started. Each gate must pass before the next phase is funded. Recommended architecture is stated at the end.

## Gate 0 — Obtain the executable (BLOCKER)
- Need: `game_scarlett_master.exe` (layout chunk 1001) in a form readable as a PE file, plus its exact version matching 1.0.2.1 (compare against `Catalog000.bin`/package identity).
- This research does not provide, and the project must not use, methods that defeat console code protection, licensing or platform keys. Practical routes are the owner's to determine (e.g. a dump method that legitimately yields the already-decrypted executable, or an official PC edition if one exists — the package lists none).
- Exit criterion: file present, `MZ`/PE32+ verified, SHA-256 recorded, original untouched (work on copies).

## Gate 1 — Complete the static analysis (small effort, decisive)
1. Install Ghidra (or equivalent) and import the exe (+ the DLLs) with the x86-64 loader.
2. Dump import/export/TLS-callback/relocation/exception tables (re-run `tools/pescan.py` on the exe).
3. Enumerate every non-Windows import (candidates: `xmem`, `d3d12_xs`, `xgameruntime`/GDK, others) and every `LoadLibrary*`/`GetProcAddress` string.
4. Identify graphics bring-up, shader loading (format!), archive-reader entry points, memory manager.
5. Update `xbox-api-analysis.md`, `graphics-analysis.md`, `feasibility-report.md`.
- Exit criterion: complete import list; shader format known; Xbox-D3D12-extension usage list known. **Decision: go / no-go.**

## Gate 2 — Data containers (parallelisable with Gate 1)
- Document RPF `9FPR` and TTPF `RDS5` headers. (Update: no `.rpf` has a readable TOC — see `rpf-header-analysis.md`; only the 64-byte plain header is documented. Reading entries requires the engine's own decryption, i.e. the exe.)
- Determine, from the exe's reader code, whether the Xbox archives are decrypted by the engine at run time. If so the engine code can be reused as-is (no need to reimplement the container formats).
- Exit criterion: know whether archives can be consumed unmodified by the original code.

## Phase 3 — Loader + stub-DLL prototype (only after Gate 1 go)
1. Use the stock Windows loader; place shim DLLs `xmem.dll`, `d3d12_xs.dll` (+ any others) next to the exe.
2. `xmem.dll`: allocation/attribute translation; log unknown attributes.
3. `d3d12_xs.dll`: forward the two public exports to `d3d12.dll`; add a tracing facade for all other entry points so the first run is a *call-trace*, not guesses.
4. Only introduce a custom PE loader if Gate 1 shows non-standard binaries.
5. Success = process reaches the first unresolved API and logs it (no gameplay yet).

## Phase 4 — Platform services
Stub GDK runtime (init, task queues, user/profile, store/licence, save game, package/chunk queries) against the documented PC GDK semantics for offline single-user mode; define behaviours from observed calls only.

## Phase 5 — Graphics backend
Order: device/queue/swap-chain bring-up (PC D3D12) → memory model → shader pipeline conversion (source/IR dependent) → resource tiling conversion → ray tracing via standard DXR (replace rehydrate) → upscaler replacement. Gate: shader format must be portable.

## Phase 6 — Audio, video, input, networking
XAudio2 (native); PC Bink 2 to replace Bink2Scarlett; input mapping; WinHTTP stack as-is; online features out of scope initially.

## Phase 7 — Stability/performance
Instrumented runs, memory-model validation, threading/affinity tuning.

## Recommended compatibility architecture
**Game-specific shim layer over the stock Windows loader** (not a Wine-style general runtime, not a full emulator):
- Shim DLLs with the original names (`xmem.dll`, `d3d12_xs.dll`, GDK runtime) exporting the exact symbols imported by the exe/DLLs, forwarding to Windows where an equivalent is proven, tracing/stubbing otherwise.
- A D3D12 translation facade for Xbox extensions (largest component).
- Optionally a launcher that supplies the process environment (identity/licensing shims for offline use).
- Original game code and data archives left untouched.

## Recommended implementation order
1. Gate 0 (get exe) → 2. Gate 1 (static analysis) → 3. Gate 2 (containers) → 4. stub DLLs + call-trace → 5. platform services → 6. graphics → 7. audio/video/input → 8. polish.

## Alternative if Gate 0 or Gate 1 fails
Stop XboxCompat for this title; the result of this phase (documented unknowns) stands as the final finding. No amount of work on the present files alone can run the game.
