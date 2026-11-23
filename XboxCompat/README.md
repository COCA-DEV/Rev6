# XboxCompat — compatibility base (v0.1, pre-executable)

Windows shim DLLs that stand in for Xbox-only modules the dumped game files import. Written from the evidence in `../docs/research/` (read `re-addendum-ghidra.md` first). The game executable (`game_scarlett_master.exe`) is **not in the dump**, so nothing here has been run against the game; coverage is limited to what the 16 present DLLs import.

## What exists

| Module | Status | Notes |
|---|---|---|
| `xmem.dll` | **Implemented, self-tested** | `XMemAlloc`, `XMemFree` (aligned CRT heap; alignment from attribute bits 24–28, zero-fill from bit 31 — *assumed* Xbox 360-style layout, MEDIUM confidence, consistent with the two attribute constants seen in the binaries), `XMemVirtualQuery` (valid/invalid only; the 0x40-byte output layout is unknown, so it is zero-filled and never claims GPU memory), `XMemGetWorkingSetStatistics` (returns FALSE = unsupported; all observed callers treat it as optional telemetry). |
| `d3d12_xs.dll` | **Implemented (forwarders only)** | `D3D12SerializeVersionedRootSignature` and `D3D12CreateRootSignatureDeserializer` are linker-forwarded to the system `d3d12.dll` (verified: same address). No Xbox device-creation or `D3D12XBOX_*` extension is provided — none is imported by the present DLLs and their signatures are unknown. |
| Tracing | Implemented | Set `XBOXCOMPAT_LOG=C:\path\trace.log` to log every shim call (pid, tid, arguments). The first run with the real game should be a call trace. |
| Self-test | `build\bin\xc_selftest.exe` | Loads only the shims built here + system `d3d12.dll`. 14/14 checks pass. |
| Static check | `tools\check_imports.py` | Confirms that, with these shims, **every import of the 16 present DLLs resolves** (no DLL from the dump is loaded). |

## What does NOT exist yet (and why)

| Item | Reason |
|---|---|
| Replacement for `Bink2Scarlett.dll` | Needs RAD's PC Bink 2 runtime (not in dump, not redistributable by me). Its 74 export names are listed in `../docs/research/data/pe.json`; a forwarding DLL can be generated once the PC binary is supplied and its exports are compared. |
| `XboxBvhBuilder.dll` / `amd_fidelityfx_upscaler_xbox.dll` behaviour on PC | Scarlett-specific (XDXR BVH layout, precompiled FSR4 pipeline states loaded via `DeserializeComputePipelineStateX`). Their imports now resolve, but they cannot do useful work on a PC GPU. A decision (rebuild BVHs with standard DXR / substitute another upscaler) must wait for the exe. |
| `D3D12XBOX_*`, Xbox device creation, GDK runtime (`XGameRuntime`: users, store, saves, task queues), input, Live | No evidence of the exact API surface without the exe's import table. Adding guesses would be fabrication. |
| Launcher / loader | Probably unnecessary (stock Windows loader + shims next to the exe), to be confirmed in Gate 1. |
| `.rpf` / `.ttpf` readers | Index of every `.rpf` is encrypted at application level; needs the engine code. |

## Build / test

```powershell
.\build.cmd                 # MSVC (VS 18) + CMake + Ninja -> build\bin\{xmem.dll,d3d12_xs.dll,xc_selftest.exe}
.\build\bin\xc_selftest.exe
python -I tools\check_imports.py ..\docs\research\data\pe.json build\bin
```

To use the shims, place `xmem.dll` and `d3d12_xs.dll` in the same directory as the module that imports them (they are not copied into the dump automatically).

## Rules this base follows
- Only evidenced APIs are implemented; unknowns are stubbed to a safe, *documented* failure value, never invented behaviour.
- Every deviation from Xbox behaviour is stated in the source header of the module.
- No code from the dump is copied; no protection or licence checks are touched.

## Next steps once `game_scarlett_master.exe` exists
1. Import it into Ghidra; run `tools/pescan.py` on it; list all non-Windows imports.
2. Add each missing API as a traced stub, then implement by evidence.
3. Re-run `check_imports.py` against the exe's imports.
