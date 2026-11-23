# RPF (`9FPR`) header analysis

Scope: the 22 `.rpf` archives in the dump (12 top-level, 10 under `pack/`). Method: read the first 0x400 bytes of each (`tools` scripts inline in this session; reproducible with `python -I` + `struct`). **No decryption, key search or cryptanalysis was attempted**; only plain header fields and statistical observations are reported.

## 1. Plain header (bytes 0x00–0x3F), all little-endian (HIGH for values, LOW–MEDIUM for meaning)

| Offset | Size | Observed | Meaning |
|---|---|---|---|
| 0x00 | 4 | `39 46 50 52` in all 22 | magic ("9FPR"; version "RPF9" is inferred) |
| 0x04 | u32 A | varies (0x260 … 0x1b070) | a size; A − B ∈ {0x20, 0x30, …} for small files (header+TOC extent? LOW) |
| 0x08 | u32 B | varies | a size slightly smaller than A (TOC length? LOW) |
| 0x0C | u32 C | varies (0x40 … 0x1d2e0) | a second size/count-like value (LOW) |
| 0x10 | 8 B | unique per file | opaque identifier/hash/IV-like value (LOW) |
| 0x18 | u32 | `0x00047A00` in all | constant (format constant) |
| 0x1C | u32 | `0x00000150` in all | constant |
| 0x20 | u16 | 3, 4, 5, 6 or 7 | small enumerated value (LOW) |
| 0x22 | u16 | 1 in all | |
| 0x24 | u32 | 2 … 2078 | count-like; grows with archive size (`levels.rpf` 2078, `common` 418, `appdata0` 2) → plausible entry/top-level-item count (LOW–MEDIUM) |
| 0x28 | u32 | one of 4 values: `0xd98004d5`, `0xda72573e`, `0xc0a92754`, `0xd5c19f6b` | category/selector-like; same value shared by unrelated archives (e.g. `script`, `story000_script`, `audio` = `0xc0a92754`) (LOW) |
| 0x2C | 4 | `01 0f 09 00` or `02 0f 09 00` | version/flags variant |
| 0x30 | u32 | `0x10` in all | constant |
| 0x34–0x3F | 12 | zero | padding |

## 2. Body (from 0x40)
- Entropy over the A/B-sized region right after the header is **7.47–8.00 bits/byte for every archive**, including the smallest (`appdata0` 7.75, `core_licenses_data` 7.70, `story000_bvh4` 7.76). **No archive has a plaintext TOC.**
- **The first 32 bytes at 0x40 are byte-identical in all 22 archives** (`5f08daab ecbdd402 58c35168 07024c24 fb9f7567 55ef4be4 58785bfe d8aa6989`); divergence starts at 0x60. Observation: identical leading ciphertext implies the same plaintext prefix under the same key/mode across files (deterministic, non-chained start). It is a fingerprint of the container's protection layer, not a decoded value.
- Files end with arbitrary-looking bytes (no readable trailer).

## 3. Consequences
1. The index of every archive is protected at the application level, in addition to the console package encryption. The key/algorithm are not in the dump; they are expected to live in the missing executable (MEDIUM) or its loaded modules. Retrieving them is outside this project's rules.
2. Without the engine, the contents of `.rpf` cannot be listed or converted. **Gate 2 can only be completed from the exe** (reader code), not from the archives.
3. The earlier claim (dump-structure §3.1 as first written) that some TOCs were readable was wrong; corrected there.
4. Useful non-secret facts for the future: the 64-byte header layout above, per-archive count-like value (0x24), archive categories (0x28/0x20), and the constants `0x47A00`/`0x150` — a loader/identifier for the format can be written to *recognise* an RPF9 without decrypting it.

## 4. Not done
TTPF (`RDS5`) headers were not re-examined beyond the first-pass notes in `dump-structure.md`; payload entropy there (7.0–7.4) is lower than RPF TOCs, suggesting compression rather than encryption — UNVERIFIED.
