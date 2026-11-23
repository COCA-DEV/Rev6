# Review of ItsNotRexed/Leonida (third-party project)

Date: 2026-11-23. Reviewed commit `5d96ea83937866d9ad75691339ddfbf99c262722` (shallow clone, no submodule auto-init, git hooks disabled) and the pinned submodule `breadbbbb/rpf9-explorer` @ `e2939175c36a02d6ed25fa2c217b9d6ddcb8b516`. **Static reading only: nothing from the repo was built or executed.** Clone kept outside the project, in the session scratchpad.

## What it is
"Native PC recompilation" of the Xbox Series build: load the console PE with a custom loader (`gta6rt --run`), reimplement the console system DLLs as shims (xmem, d3d12_xs → Vulkan, xgameruntime, GameInput, WinHTTP-offline, …) and translate the console's precompiled RDNA2 shaders to SPIR-V. License **GPL-3.0**. 2,208 files: 1,041 tests, 706 runtime (C++), 300 tools (Python/C#), 84 docs. README status: **"Early. The game does not boot yet."** Its own measured boot chain (docs/retail_boot_chain.md) stops at "stop 13", a D3D12 descriptor-heap handle assertion.

## Consistency with our independent findings (HIGH)
- Same executable: they cite SHA-256 `e95020b2…8993`, identical to our copy.
- Same first stops: `D3D12ConfigureVirtualMemoryX`, `XMemVirtualAlloc` (24 GiB windows, 64 KiB page mode), physical-page family, then `DStorageGetFactory` null fatal assert. Their parameter orders and constants match what we traced.
- Same conclusion about encrypted RPF tables of contents (their tools read only the data area; "no keys, no TOC decryption").

## Security review (static; limits below)
| Check | Result |
|---|---|
| Committed binaries | 1 (`assets/logo.png`). No DLL/EXE/ZIP/blobs. |
| Obfuscation / `eval` / `exec` / encoded payloads | None in sources; one `base64.b64decode` in `tools/ped_assemble.py` for a user-supplied value. |
| Network use | Build only: pinned SDL3 and Vulkan-Headers archives **with SHA-256** (`runtime/CMakeLists.txt`), Python 3.12.10 installer from python.org **only after a Y/N prompt, with SHA-256 check** (`Build.bat`), `git clone` of llvm-project (`scripts/build_llvm_mc.ps1`), CI downloads glslang from Khronos. `tools/gallery.py` is a local server that rejects non-localhost hosts. No webhooks, telemetry, credentials, persistence or registry writes found. |
| Runtime network | `runtime/shims/winhttp_offline.cpp` answers WinHTTP in-process and refuses all connections ("nothing here goes online"); good property for running the game. |
| Deletions | `make_game.py` deletes only inside the chosen `--out`/work folder (checked the `rmtree`/`unlink` sites). |
| Process creation | Build orchestration (`make_game.py`: Python tools with `-I`, `cmake`, `dotnet`, `git submodule update`, `ffmpeg`, `spirv-*`) and the runtime re-launching itself suspended to reserve a base address. No injection into other processes found. |
| Keys / decryption | Code and docs consistently state nothing decrypts or carries keys; no key-like constants found in source. The submodule recognises encryption types (`0x0FFFFFF9` = "AES", `0x0FEFFFFF` = "NG") and refuses to extract encrypted members without keys. |
| Submodule `rpf9-explorer` | C# (Core net8.0, App net10.0-windows), 71 files, one NuGet dependency (`BCnEncoder.Net 2.3.0`), no pre/post-build hooks, no binaries. The App launches `ffmpeg.exe`/`opus-preview.exe` for audio/video previews only. |

## Caveats / residual risk
- Not exhaustive: pattern scan of all files plus manual reading of the build scripts, loader/shim entry points and the submodule's build files. The 1,041 test files, most of the 706 runtime files and the 300 tools were not read line by line. A build compiles ~700 C++ files and runs ~300 Python tools; a defect or hidden behaviour there would not necessarily be caught by this review.
- The repo is 3 days old (created 2026-11-20) and shows 22k stars and PR numbers above 6,800; popularity numbers can be inflated and are not evidence of trust.
- GPL-3.0: copying their code into XboxCompat obliges us to GPL-3.0 on distribution. Using their docs as reference only (as done here) does not.
- Building needs: MSVC + Windows SDK (present), CMake (present), Python ≥ 3.12 (present: 3.14), .NET SDK 8+ (not checked), Vulkan SDK, LLVM mc build (large git clone). Full pipeline translates 26,503 shaders (hours) and is not required just to try booting the runtime.

## Recommendation
Reasonable to build **only the runtime** (`gta6rt`) in an isolated folder, running as a normal user, with the game's executable and packages read-only, as the next experiment; skip the asset/shader stages at first. Before doing so: pin to the reviewed commit, and either build offline from a copy that has the SDL3/Vulkan-Headers archives already hash-checked, or accept those two pinned downloads.
