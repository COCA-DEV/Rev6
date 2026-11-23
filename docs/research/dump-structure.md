# Dump Structure

Root: `D:\xbox series dump\GTA6.Xbox.v1.0.2.1` — 109 files (before `docs/`), 223,880,935,469 bytes (≈208.5 GiB). Format identification used magic bytes, not extensions.

## 1. Top-level inventory

| Category | Files | Signature (HIGH) | Notes |
|---|---|---|---|
| PE32+ DLLs (16) | `Bink2Scarlett`, `XboxBvhBuilder`, `XCurl`, `libHttpClient.GDK`, `amd_fidelityfx_loader_xbox`, `amd_fidelityfx_upscaler_xbox`, `concrt140`, `msvcp140`, `msvcp140_1`, `msvcp140_2`, `msvcp140_atomic_wait`, `msvcp140_codecvt_ids`, `vccorlib140`, `vcomp140`, `vcruntime140`, `vcruntime140_1` | `4D 5A` (MZ) | See `dll-inventory.md` |
| Executables | **none** | — | `game_scarlett_master.exe` is declared but absent |
| RPF archives (top level, 12) | `anim`, `appdata0`, `audio`, `common`, `data`, `levels`, `movies`, `navmeshes`, `packs`, `script`, `shaders`, `textures` (`.rpf`) | bytes `39 46 50 52` = ASCII `9FPR`; as LE u32 `0x52504639` (= "RPF9" reversed) | Proprietary Rockstar archive; version tag "9" inferred (MEDIUM) |
| RPF archives (`pack/`, 10) | `core_bvh4`, `core_licenses_data`, `core_restofworld`, `core_restofworld001`, `shared_minigame000`, `shared_minigame000_bvh4`, `story000`, `story000_script`, `story000_bvh4`, `story000_restofworld` | same | DLC-style "packs" |
| TTPF files (~55) | `data/ttdb/**`, `pack/*/data/ttdb/**` | bytes `52 44 53 35` = ASCII `RDS5` | Proprietary texture/"ttdb" streaming packs (name is from path; contents unknown). Magic is `RDS5`, not "TTPF" — extension is not the format name. |
| XVD | `gameos.xvd` (348,069,888 B) | `msft-xvd` at offset 0x200 | Xbox Virtual Disk; **not in layout file** |
| Code catalog | `Catalog000.bin` (815,104 B) | `4D 5A` + 1 section, Subsystem = 17 | `IMAGE_SUBSYSTEM_XBOX_CODE_CATALOG`; **not in layout file** |
| GDK metadata | `MicrosoftGame.Config` (XML, UTF-8 BOM), `appxmanifest.xml`, `layout_3202719e-…_xs.xml`, `microsoft_gameconfig.bin`, `resources.pri` | `<?xml`, `regf`, `mrm_pri2` | `microsoft_gameconfig.bin` is a Windows registry hive (`regf`) holding a compiled copy of the Config (strings include a build temp path `Local\Temp\2\MKPE100.tmp\gc.bin`) |
| Other | `Update.alignmentchunk` (1 byte `0x30`), 5× `xbs_*.png`, `readme.md` | PNG / text | Alignment chunk is a GDK "Launch"-marker chunk (layout chunk `3009`) |

SHA-256 of all non-archive files: `data/sha256.txt`. Archives (>200 GB) were not hashed.

## 2. Package layout (from `layout_…_xs.xml`, HIGH)

| Chunk | Content | On disk |
|---|---|---|
| 1000 | Config, PNGs, `resources.pri`, `appdata0.rpf` | yes |
| **1001** | **`game_scarlett_master.exe` (only file in its chunk)** | **NO** |
| 1002 | 16 DLLs | yes |
| 1003 | all `data/ttdb/**/*.ttpf` | yes |
| 1004–1014 | `common, movies, shaders, anim, data, levels, navmeshes, packs, textures, audio, script` `.rpf` (one per chunk) | yes |
| 3000–3008 | `pack/*` content (story000, bvh4, restofworld, minigame, licenses…) | yes |
| 3009 `Marker="Launch"` | `Update.alignmentchunk` | yes |

Chunk 1001 being a dedicated chunk is consistent with the exe being split out and withheld/missed by the dumping method. `Marker="Launch"` on 3009 indicates the console can start the title once chunks up to that point are installed (MEDIUM: GDK semantic from recollection).

Files present but absent from the layout: `appxmanifest.xml`, `Catalog000.bin`, `gameos.xvd`, `layout_*.xml`, `microsoft_gameconfig.bin`, `readme.md` — i.e. they are package/system artefacts of the Xbox install, not game content chunks.

## 3. Container formats

### 3.1 `.rpf` (`9FPR`)
First dword = magic; next dwords at 0x04/0x08/0x0C are three varying values (e.g. `anim.rpf`: `0x4660, 0x3C00, 0x2A90`; `appdata0.rpf`: `0x360, 0x340, 0x40`) — plausibly TOC/name-table/size fields, but **semantics unverified (LOW)**. Entropy of bytes `0x40–0x1000`: ~7.95 bits/byte for large archives (`anim, audio, common, data, levels, movies, packs, shaders, core_bvh4, story000, shared_minigame000`) → TOC is encrypted or compressed. **CORRECTION (see `rpf-header-analysis.md`):** the low entropy figures I first reported for `appdata0, script, textures, navmeshes, core_licenses_data, story000_script, story000_bvh4, core_restofworld001, shared_minigame000_bvh4` were an artefact of measuring a fixed 4 KiB window that includes zero padding in small files. Measured over the actual header/TOC span, **all 22 `.rpf` archives have a high-entropy (7.5–8.0) TOC**, so none has a readable index. Whether RPF encryption keys live in the missing exe is UNKNOWN; not pursued (no key extraction).

Largest: `levels.rpf` 76.2 GB, `audio.rpf` 28.5 GB, `story000.rpf` 20.0 GB, `movies.rpf` 8.8 GB, `core_bvh4.rpf` 8.3 GB, `navmeshes.rpf` 6.7 GB.

### 3.2 `.ttpf` (`RDS5`)
Header dwords: `RDS5`, u32 (e.g. `0x606` for `ttdb_graphics`), u32 (varies, equals roughly a size/offset), u32 `0x16000000/0x16000001`, u32 (small count?), … Values correlate with file size (`ttdb_graphics.ttpf`: field2 `0x077db000` ≈ 125 MB vs file 34 MB, so not file size — LOW). Fixed 4 KiB-aligned file sizes. Entropy ~7.1 → compressed/encrypted payload. Directory names indicate content domains: graphics, interiors, lighting, maps, peds, props, terrain (+`image_based`), ui, vehicles, vfx, weapons.

### 3.3 `gameos.xvd`
- `msft-xvd` at 0x200 (HIGH). Offset 0x208 volume flags = `0x1`; 0x20C format version = `3`; 0x218 drive size = 536,870,912 (512 MiB) vs file size 348,069,888 (smaller; sparse/dynamic layout suspected, MEDIUM). Field offsets from community XVD header documentation (MEDIUM).
- Header 0x0–0x1FF entropy 7.6 (signature block); body entropy 6.7–7.99 → encrypted/compressed payload. 0 occurrences of `MZ\x90\x00` in the first 64 MiB.
- Role: the manifest depends on `Microsoft.GameOs 10.0.18362.0` (`uap7:OSPackageDependency`), and the file is named `gameos.xvd`. It is not part of the game's layout. Contents unverified; it was **not** decrypted or mounted (would require platform key material — out of scope). It cannot be assumed to contain the game exe.

### 3.4 `Catalog000.bin`
Details in `executable-analysis.md` §5.

## 4. Package identity (HIGH — `MicrosoftGame.Config`, `appxmanifest.xml`)

- Title: Grand Theft Auto VI; publisher Rockstar Games; version 1.0.2.1
- `Identity Name="RockstarGamesInc.28872443D20A7"`, TitleId `7952987A`, MSAAppId `000000004060F900`, StoreId `9NL3WWNZLZZN`, protocol `ms-xbl-7952987a`
- Single executable: `game_scarlett_master.exe`, `Id="GTAO"`, `TargetDeviceFamily="Scarlett"`, `IsDevOnly="false"` (so a retail/"master" build)
- `PersistentLocalStorage` 2048 MB; `VirtualMachine`: SMT enabled; `XboxLockhartTitleMemory`/`XboxAnacondaTitleMemory` = `Advanced` (Series S / Series X titles memory tiers; exact meaning of "Advanced" MEDIUM/UNVERIFIED)
- Capabilities: `internetClient`, `microphone`; `TargetDeviceFamily Windows.Universal MinVersion 10.0.18362.0`
- 39 resource languages (en-*, zh-*, fr-*, de-*, it-IT, ko-KR, pl-PL, pt-*, ru-RU, es-*)
- **There is no Desktop/PC executable entry.** Only `Scarlett`.

## 5. Directory tree (abridged)

```
/                      12 .rpf, 16 DLLs, metadata, gameos.xvd, Catalog000.bin
data/ttdb/{graphics,interiors,lighting,maps,peds,props,terrain,ui,vehicles,vfx,weapons}/*.ttpf
pack/core_bvh4  core_licenses  core_restofworld[/data/ttdb]  core_restofworld001[/data/ttdb]
pack/shared_minigame000[/data/ttdb]  shared_minigame000_bvh4
pack/story000[/data/ttdb]  story000_bvh4  story000_restofworld
```
