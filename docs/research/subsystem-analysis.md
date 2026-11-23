# Subsystem Analysis

For each subsystem: evidence in the dump → status. "Essential" = the title cannot run without it (inferred).

| Subsystem | Evidence | Essential? | Windows mapping | Status/Conf. |
|---|---|---|---|---|
| **Audio** | Bink2Scarlett imports `XAudio2_9!XAudio2Create` (HIGH); `audio.rpf` 28.5 GB (format unknown); `appxmanifest` microphone capability | yes | XAudio2 exists on Windows 10 (HIGH). Engine audio mixing/codec is in the exe and `audio.rpf` (UNKNOWN). Microphone → WASAPI/`Windows.Media.Capture` (voice chat; MEDIUM) | partial evidence |
| **Video** | Bink2 Scarlett (74 exports), `movies.rpf` 8.8 GB (container UNKNOWN; likely `.bk2`) | yes (intro/cutscenes) | PC Bink 2 (not in dump) | MEDIUM |
| **Input** | **no evidence** in present files (no `xinput`, `Windows.Gaming.Input`, `GameInput` import). GDK titles typically use GameInput/`XInput`-like APIs; unverified | yes | XInput/GameInput on PC | UNKNOWN |
| **Networking** | `libHttpClient.GDK` (HTTP + WebSocket), `XCurl` (libcurl over WinHTTP) — both HIGH. No Winsock import in any present DLL. Online multiplayer layer (sockets, party, NAT, Xbox Live) is in the exe | online features: probably (title has TitleId, MSA app, `internetClient`) | WinHTTP present; Xbox Live auth/session services (XUser/XSAPI/Party/MPSD) require Microsoft services — not replicable by a local shim; offline/single-player shims possible in principle | HTTP HIGH; rest UNKNOWN |
| **Filesystem** | Content is proprietary archives (RPF `9FPR`, TTPF `RDS5`). The engine's archive reader, decompressor and (possible) decryption live in the exe. Package layout (chunks) via GDK. `PersistentLocalStorage` 2048 MB (save/persistent data). `appdata0.rpf` (8.9 KB) small | yes | Windows file APIs; needs the reader — reimplement (format unknown) or run the original code | UNKNOWN internals |
| **Memory** | XMem APIs (4); `VirtualMachine` `Advanced` title-memory tiers; SMT enabled; 2 GB persistent storage; DLLs assume 64-bit address space | yes | `VirtualAlloc` family, but unified-memory (16 GB shared CPU/GPU) assumptions and GPU-visible allocations are not replicable 1:1 | partial |
| **Threads/sync** | Imports are standard: SRW locks, condition variables, threadpool, fibers (`FlsAlloc`), `SetThreadAffinityMask`, `QueryPerformanceCounter`. All resolve on host (HIGH). Bink uses `BinkUtilCPUs` + async threads + affinity masks | yes | 1:1 (HIGH). Thread affinity assumptions for a fixed 8-core/16-thread SMT console (SMT enabled) → scheduling differences | HIGH for DLL layer |
| **System services** | XCurl imports `RegisterAppStateChangeNotification` (PLM suspend/resume), ETW (`RegisterTraceGuidsW`, `EventRegister`) | yes (lifecycle) | Win32 apiset exists; behaviour differs for unpackaged exes | MEDIUM |
| **Runtime initialisation** | MSVC 14.29 CRT/STL (`amd64.onecore`), C++ EH (VCRUNTIME140_1), WinRT core lib (`vccorlib140`) listed in the layout (usage UNKNOWN) | — | standard | HIGH for DLLs |
| **Platform identity & capabilities** | `TitleId 7952987A`, `MSAAppId 000000004060F900`, `StoreId 9NL3WWNZLZZN`, `ms-xbl-7952987a` protocol, `OSPackageDependency Microsoft.GameOs 10.0.18362.0`, `EntryPoint="GamingProxyApp.Application.EntryPoint"`, caps `internetClient`/`microphone`, 39 locales | yes (launch/entitlement) | PC GDK packages use different identity, `Gaming.Desktop.x64` platform and licence checks; the Scarlett identity cannot be satisfied by Windows | HIGH facts / MEDIUM implications |
| **Licensing/entitlement** | Catalog (`Catalog000.bin`) + XVC packaging imply console-enforced integrity/entitlement. Not analysed, not bypassed (rules) | gate | out of scope | UNKNOWN |

## Essential-subsystem ranking (for planning)
1. Executable code itself (MISSING) → 2. Archive reading/decryption (RPF/TTPF; UNKNOWN) → 3. GPU backend + shader pipeline (UNKNOWN formats) → 4. GDK runtime/Live (UNKNOWN) → 5. Memory model (XMem) → 6. Audio/Video middleware (PARTIAL; mostly portable) → 7. HTTP stack (portable).
