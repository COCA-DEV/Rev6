# Executable Format Analysis

## 1. The main executable — absent (HIGH)

Evidence chain:
1. `MicrosoftGame.Config`: `<Executable Name="game_scarlett_master.exe" Id="GTAO" TargetDeviceFamily="Scarlett" …/>`.
2. `appxmanifest.xml`: `<Application Id="GTAO" Executable="game_scarlett_master.exe" EntryPoint="GamingProxyApp.Application.EntryPoint">`.
3. `microsoft_gameconfig.bin` (registry hive) contains the same string.
4. `layout_…_xs.xml` chunk `1001` → `game_scarlett_master.exe` (source `..\..\content\`).
5. Script `tools/layoutcheck.py`: 104 layout entries, **1 missing: `1001 / game_scarlett_master.exe`**. Glob `**/*scarlett_master*` → no results.
6. Only 16 PE files exist (all DLLs plus `Catalog000.bin`). None is a game-sized executable; the largest DLL is `libHttpClient.GDK.dll` (976 KB).

Consequence: **the exact format of the game executable cannot be determined.** Nothing below about the exe is observed; statements about it are explicitly labelled inference. `gameos.xvd` (§6) is not shown to contain it.

Possible (unverified) reasons for the absence: the dumping method skipped the exe because it is code-integrity protected (the console validates code pages against the catalog), or it was excluded from the "decrypted" set. Which reason applies is UNKNOWN; recovering it is outside this research phase (see roadmap Gate 0).

## 2. Format of the 16 present images (HIGH — `tools/pescan.py`, `data/pe.json`)

All 16: PE32+ (`OptionalHeader.Magic 0x20B`), `Machine 0x8664` (AMD64/x86-64), DLL characteristic set, MajorOSVersion 6.0, all have `.pdata` (x64 unwind/exception tables), `.reloc` (ASLR/relocations), Load-Config directory, and no CLR header (native code).

| Image | Subsys | Entry RVA | Sections | TLS | Notes |
|---|---|---|---|---|---|
| Bink2Scarlett.dll | 2 GUI | 0x2AC1C | .text .rdata .data .pdata **.xbld** .reloc | none | PDB path `C:\devel\projects\bink\build\Bink2Scarlett.pdb`; TS 2023-02-08 |
| XboxBvhBuilder.dll | 2 | 0x227CC | .text .rdata .data .pdata **.xbld** .rsrc .reloc | yes (cb VA 0x1800242D0) | TS 2026-03-27 |
| amd_fidelityfx_loader_xbox.dll | 3 CUI | 0x18D0 | no `.xbld` | none | v1.0.2.0; PDB `…\Gaming.Xbox.Scarlett.x64\Release\amd_fidelityfx_loader_xbox.pdb` |
| amd_fidelityfx_upscaler_xbox.dll | 3 | 0x26780 | .xbld | yes (0x1800283E0) | v3.1.5.0; TS 2058 (see §4) |
| XCurl.dll | 3 | 0x17B0 | .xbld | none | v2604.5.0.0; Authenticode directory present; TS 1972 (§4) |
| libHttpClient.GDK.dll | 2 | 0x11F0 | .idata .gfids .00cfg minATL .tls .xbld | yes (0x1800AA448) | v2.3.4; Authenticode present; TS 2026-08-31 |
| concrt140, msvcp140(+_1,_2,_atomic_wait,_codecvt_ids), vccorlib140, vcomp140, vcruntime140(+_1) | 3 (vcomp 2) | — | standard | none | MSVC 14.29.30157.0 **`amd64.onecore`** builds (PDB path), Authenticode present |

Key: the `.xbld` section (present in 7 images, the ones built with the Xbox GDK toolchain) is an Xbox-toolchain marker (MEDIUM; semantics unverified). TLS directories are present in 3 images; TLS callback arrays were not walked.

So the executable format used by every present binary is **standard PE/COFF PE32+ x86-64**, not a proprietary Xbox format (HIGH for these 16). Xbox One/Series GDK binaries are PE (MEDIUM from public knowledge); the missing exe is therefore expected to be PE32+ as well (MEDIUM — inference only).

Exception tables: all have an exception data directory (`.pdata`, x64 table-based unwinding). Runtime init is MSVC CRT (`VCRUNTIME140`, `VCRUNTIME140_1` for /EHa C++ x64 frame handlers).

## 3. Can a conventional Windows loader load them? (HIGH for static resolution)

The Windows loader needs every import resolved by name. Using a host test (`tools/resolve.py`: `LoadLibraryExW(name, NULL, LOAD_LIBRARY_SEARCH_SYSTEM32)` + `GetProcAddress` against the host's own System32 DLLs; no dump file loaded):

| Resolution | DLLs imported |
|---|---|
| Host OK, every named function found | 55 system/API-set DLLs (`api-ms-win-core-*`, `api-ms-win-crt-*`, `KERNEL32`, `ADVAPI32`, `WINHTTP`, `CRYPT32`, `OLEAUT32`, `XAudio2_9`, `api-ms-win-core-psm-appnotify`, `…-winrt-*`, `…-eventing-*`) |
| Bundled in dump | `MSVCP140`, `VCRUNTIME140`, `VCRUNTIME140_1` |
| **Not present on Windows** | **`xmem.dll`** (importers: Bink2Scarlett, XboxBvhBuilder, amd_fidelityfx_upscaler_xbox), **`d3d12_xs.dll`** (XboxBvhBuilder, amd_fidelityfx_upscaler_xbox) |

Therefore, of 16 DLLs: 13 have fully resolvable static imports on stock Windows (CRT set + XCurl + libHttpClient + FFX loader; the CRT DLLs resolve each other from the dump directory); **3 fail with "module not found"** (`Bink2Scarlett`, `XboxBvhBuilder`, `amd_fidelityfx_upscaler_xbox`). The FFX loader has no static import of the upscaler (it imports `LoadLibraryExW`, so it presumably loads it at run time — MEDIUM), which would then fail. Caveat: load success ≠ correct behaviour (e.g. `RegisterAppStateChangeNotification` in XCurl exists in the apiset but needs a packaged-app context; UNTESTED, nothing was executed).

`ord1` of `XAudio2_9.dll` was resolved on the host to `XAudio2Create` (HIGH).

Consequence for the missing exe (MEDIUM, inference): if it is a PE32+ whose only non-Windows imports are Xbox DLLs (`xmem.dll`, `d3d12_xs.dll`, plus possibly `xgameruntime`-family), a conventional loader plus **shim DLLs placed in the search path** would be enough — a custom PE loader is probably unnecessary. This cannot be confirmed without the exe's import table.

## 4. Anomalous timestamps (HIGH observation, MEDIUM interpretation)
`XCurl.dll` TS 1972-10-25 and `amd_fidelityfx_upscaler_xbox.dll` TS 2058-07-13 are outside plausible build dates; `Catalog000.bin` TS = 0. Debug directory entry type 16 (`IMAGE_DEBUG_TYPE_REPRO`) is present in XCurl and the upscaler → deterministic builds replace TimeDateStamp with a hash. Don't use these timestamps for dating.

## 5. `Catalog000.bin` (HIGH structure, MEDIUM meaning)
`MZ` header, `e_lfanew=0x40`, `Machine 0x8664`, 1 section (RVA 0x1000, raw size 0xC6000, characteristics 0x40000000 = read-only data), no imports/exports/entry point, `Subsystem = 17` = `IMAGE_SUBSYSTEM_XBOX_CODE_CATALOG`, SizeOfImage 0xC7000. The 0xC6000-byte body has entropy ~7.69 → looks like a hash/signature table or encrypted block. It contains no ASCII/UTF-16 names of the dump's files. Interpretation: Xbox code-integrity catalog for the package's executable pages (so the console can verify them). It is **not loadable code** and does not substitute for the exe. It was not parsed further (hash-table parsing is not needed for compatibility, and pursuing it leans toward platform-security internals).

## 6. `gameos.xvd`
See `dump-structure.md` §3.3. XVD, version 3, encrypted/high-entropy, not mounted, not decrypted. Not an executable of the game. Whether it holds GameOS system DLLs (`xmem.dll`, `d3d12_xs.dll`, etc.) is **UNKNOWN**; if it did, those would be Microsoft system components with their own licensing and would still not be the game. Not assumed.

## 7. Items investigated for the missing exe and their status

| Item | Status |
|---|---|
| PE/COFF header, entry, sections | UNKNOWN (exe absent) |
| Imports/exports/relocs/TLS/exception tables | UNKNOWN (exe absent); DLL data above |
| Runtime init | UNKNOWN for exe; DLLs use MSVC CRT 14.29 onecore |
| Dependencies of the exe | partly inferable: the 16 DLLs are listed as game content (chunk 1002) so the exe presumably loads Bink2Scarlett, XboxBvhBuilder, FFX loader/upscaler, XCurl, libHttpClient (MEDIUM) |
