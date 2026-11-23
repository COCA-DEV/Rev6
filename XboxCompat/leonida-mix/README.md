# Leonida + XboxCompat mix (local, GPL-3.0 derivative)

`leonida-mix.patch` = our changes on top of ItsNotRexed/Leonida commit `5d96ea83937866d9ad75691339ddfbf99c262722`
(runtime/ and scripts/ only). Apply with `git apply` on a clone of that commit. **It contains code derived from
GPL-3.0 sources (Leonida and the pull requests below): if it is ever distributed, the whole must be GPL-3.0.**
Everything was reviewed statically before use (docs/research/leonida-review.md); nothing in it touches the network.

## What is in the patch
| Source | What | State |
|---|---|---|
| PR #6582 (Kam471) | `XErrorReport` in xgameruntime shim | applied cleanly |
| PR #2490 (NolanCotter) | d3d12_xs console-ABI command lists, upload arena | applied cleanly |
| PR #4348 (mariuslozo-boop) | console DirectStorage (`DStorageGetFactory`, queues, file reads) | new files + wiring applied; its CMake *test* target hunks dropped |
| PR #4313 (mariuslozo-boop) | module TLS index 0 for the game exe | applied except: CMake test hunks, a doc comment, and the thread attach/detach reorder hunk (#11 of pe_loader.cpp) — not yet ported |
| PR #6709 / #4531 | XMem 64 KiB / 2 MiB pages | **not applied as diffs; replaced by our own implementation** (below) |
| ours (XboxCompat) | `XMemVirtualAlloc`: 2 MiB mode (aligned host pages), reserve-only 64 KiB mode as address-space placeholders; physical-page pool (`XMemAllocatePhysicalPages`, `XMemMapPhysicalPages`, `…Scatter`, `XMemFreePhysicalPages`) over pagefile sections; `XMemAlloc` honours alignment/zero-fill bits; `XMemIsToolsMemAvailable`; `D3D12ConfigureVirtualMemoryX` no-op | built and run |

## Result of the first runs (sandbox copy of the exe, dump untouched)
- Unimplemented imports: 30 → 24 (remaining: audio `chad`/`xapu`/`AcpHal` ×19, `xg_xs` ×2, `XMemAllocDefault`/`FreeDefault`).
- The exe now gets through all startup memory reservations and TLS, then faults at `game_scarlett_master.exe+0x104075`
  (call chain `+0x4fac3d7` ← `+0x1e1cdc5` ← `+0x5c34ff2`): a read through a garbage pointer (`0x6e6f6974`, `0xffffffffffffffff`
  on different runs). Under the native Windows loader (our XboxCompat shims) the same exe went further, up to
  `DStorageGetFactory`, so this is specific to the gta6rt loader environment. Under analysis.

---
## Update 2026-11-23 (later): the mixed runtime reaches the project's documented frontier
Changes added after the first README section (all in `leonida-mix.patch`):
- `pe_loader.cpp`: thread attach/detach hunk of PR #4313 ported by hand (install all TLS copies including the executable's
  index-0 slot, then run callbacks; detach in reverse, executable last). **This removed the garbage-pointer crash**: the game's
  `operator new` reads its per-thread allocator from `TLS[0]+0x13a8`.
- `d3d12_xs_device.cpp`: slot 26 (`GetCustomHeapProperties`, console passes the return buffer first), slot 48 queue description
  sanitised (Flags limited to DISABLE_GPU_TIMEOUT), slot 73 console list IID `{c3827890-4024-474c-98cf-645b51dc4874}` answered by
  the list proxy, slot 133 `CreatePlacedResourceX` stand-in (committed DEFAULT-heap resource, not tied to the address), proxy slot
  table 128 -> 192.
- `xmem.cpp`: `MEM_RESERVE_PLACEHOLDER` (0x40000) and `MEM_REPLACE_PLACEHOLDER` (0x4000) forms, nested windows, physical pages
  mapped into placeholders (page 64 KiB), `XMemAlloc` alignment/zero from the attribute word.

Run 20 (sandbox copy of the exe, Radeon RX 580 through Vulkan): the exe now completes startup allocations, DirectStorage factory +
file, `D3D12XboxCreateDevice`, 4 queues, fences, 581 command lists, the placeholder/physical-page sequence and slot 133, then
stops at its own assertion right after `CreateDescriptorHeap` -> `GetCPUDescriptorHandleForHeapStart` (heap slot 9). That is
"stop 13" of the third-party boot chain: nobody has passed it yet. Nothing has been drawn or presented.
Hardware note: the RX 580 has no `VK_EXT_mesh_shader` and `maxPushConstantsSize` 128 < 144 required by the shader contract.

---
## Update 2026-11-23 (night): past "stop 13"
Findings (all measured from the retail executable by static decompilation of a handful of functions; Ghidra full auto-analysis of the
120 MB image never finishes, so single functions are decompiled with a small headless script, `-noanalysis` + `DecompileAt.java`):

1. **Descriptor-heap assertion solved.** The title's heap wrapper (FUN_141cf3280) registers a block of its own memory in a per-thread list
   keyed to allocator id 0x80 (object type 4), calls CreateDescriptorHeap, then asserts that GetCPUDescriptorHandleForHeapStart equals that
   block. The console D3D12 runtime obtains heap memory through the executable's exported `__XMemAllocationHooks__` (alloc hook = first
   qword). The proxy now calls that hook (`size = NumDescriptors * increment`, attributes `(0x80<<16)|4`) and gives the memory to the
   Vulkan layer, which uses it as the heap's CPU storage and mirrors it into the GPU arena before every ExecuteCommandLists.
2. **CPU compatibility.** The game uses CLWB (Zen 2). Ryzen 5 1600 (Zen 1) raises #UD; the runtime now emulates CLWB/CLFLUSHOPT as no-ops and
   RDPID with the processor number (vectored handler in main.cpp).
3. **Device slot 70** = console "create view from address" (resource shape, SRV-like view description + a title-memory GPU address,
   destination descriptor address); stand-in writes a null descriptor. Needs GPU-visible title memory to be real.
4. **Device slot 25** GetResourceAllocationInfo uses the console return-buffer-first convention (like 26).
5. **Next stop**: device slot 127 (console-only, beyond the PC vtable) is called by FUN_145204e60; E_NOTIMPL makes the title assert.

Not solved and structural: title memory (the placeholder/physical-page windows) is not visible to the GPU, so resources placed there (slot 133,
slot 70) are stand-ins; shaders (26,503 RDNA2 programs) must be translated to SPIR-V by the Leonida pipeline; the RX 580 lacks mesh shaders.

---
## Update 2026-11-23 (late night): render targets created, GPU limit reached
Added: device slot 127 (console CreateCommittedResource with two extra zero args; riid = a9, out = a10 because the console passes a
16-byte value inline as two stack words), PC-bit masking of console resource flags in the committed path, and **texture memory
accounting through the title's allocation hook**: the title registers a linear allocator with a fixed budget while it builds its render
targets and asserts it was consumed to within 2 MiB (FUN_14247ad10 + callback FUN_1456a2a60); the proxy now requests each texture's
64 KiB-rounded size from the hook (only when a title allocator is registered: list head at image+0x6843770, 1.0.2.1 only).
`XMemAllocDefault`/`XMemFreeDefault` are real now (VirtualAlloc): the callback treats a null base as "unallocated" and restarts its
bump pointer when it gets one.

Run 29: startup + DirectStorage + device + queues + 581 lists + descriptor heaps + two 3840x2160 RGBA8 render targets with RTVs all
succeed; the title then creates a root signature and its first compute pipeline (XboxBvhBuilder constructor, DXIL) and the Vulkan layer
refuses it: **"pipelines need 144 bytes of push constants (uniform-buffer fallback not built yet); maxPushConstantsSize 128"**. The
Radeon RX 580 (Polaris) reports 128. XboxBvhBuilder then throws a C++ exception (0xE06D7363) because its pipeline creation failed.
The fallback is the upstream project's open item (#224) and needs translator/SPIR-V changes; it is not attempted here.
Also unavailable on this GPU: VK_EXT_mesh_shader (9,282 of the 26,503 translated shaders are mesh shaders).

---
## Update 2026-11-23 (night): RX 580 boots past the BVH builder and the device bring-up (patch regenerated)
Superseded finding above: the push-constant limit is solved on the RX 580. `--pc-tail-ubo` shaders read the extra 16 bytes from a
set-1 dynamic UBO (`PcTail`, `create_pc_tail()`); `LEONIDA_FORCE_PUSH_CONSTANTS=1` overrides. All 26,573 shaders translate, including
the 52 BVH-builder compute shaders carved from `XboxBvhBuilder.dll` (`carve_dll.py` + an `index.json`; the loader also reads `bvh/`).

What actually stalled the boot (found with the new sampler + unwinder, `LEONIDA_SAMPLE_THREADS=<s>`): not a wait for an object. The
game thread sits inside the AMD driver compiling the BVH pipelines, ~54 s the first time on a Zen 1 CPU, while the title's own
watchdog (FUN_142215a60) kills the process after 30 s without a main-thread heartbeat. The title honours a "watchdog paused" byte
(image+0x1471b6330), set here by `LEONIDA_PAUSE_WATCHDOG=1` (diagnostic, only touches the process's memory, not the dump). The compile
lands in the pipeline cache: later runs take ~5 s and do not need the flag.

Then, each found by an int3/AV with the new crash chain (`[rt] int3 at ...`, `[rt] access violation at ...`):
- command signatures with a mesh dispatch (type 10 and console-only 0x69) -> mapped to a compute dispatch (`--mesh-compute` shaders).
- device slot 61 = console CreateSampler (96-byte description, dest address) -> STAND-IN, zeroed 16-byte descriptor.
- device slot 74 = registers the physically mapped pages (base, 64 KiB pages, out qword) -> STAND-IN, S_OK.
- device slot 86 is beyond the PC vtable -> was E_NOTIMPL; now STAND-IN no-op object (desc, riid, out).
- `xg_xs.dll` in the dump is a stub that only logs "not available"; `XGCreateTextureComputer`/`XGSuggestSwizzleMode` now shimmed with a
  no-op computer object (no swizzle layout is computed).
Current state (run 53): the title reaches device slot 108, `DeserializeComputePipelineStateX` fails for ~18 shaders that are not in
the translated set (other DLLs' shaders, e.g. fidelityfx/Bink: carve them like the BVH ones), and then an access violation in the
forwarded slot 108 (host `gta6rt.exe+0xfbf59`, address 0x100000389). No frame has been drawn; no loading screen exists yet.
All stand-ins above are placeholders for real behaviour (title memory is still not GPU-visible), so correct output is not expected
until they are replaced.

---
## Update 2026-11-23 (later): the title reaches its main loop and presents (patch regenerated)
Fixed since the previous note (run 69): device slot 108 = console GetResourceAllocationInfo1 (return buffer first; filled from the PC
answer per description); A8_UNORM textures (render target / UAV) stored as R8; storage usage no longer requested for depth-stencil
images (the title sets UAV on its D32S8 depth buffers; that assertion FUN_140343e80 wanted a finite size); fence slot 12 = pointer to a
CPU-visible completed-value qword (the title polls it with monitorx/mwaitx): STAND-IN mirror refreshed by one helper thread;
SetPipelineState(null) is null-safe; slot 67 clears `*out` when the pipeline cannot be created (the FidelityFX DLL does not).
Measured facts: slot 86 is **CreateGraphicsPipelineStateX(desc, ID3D12PipelineState IID, out)** (my earlier "copy helper" reading was
wrong: the "no-op object" ended up as a pipeline); it is now a null-pipeline STAND-IN that dumps the first three descriptions
(`[rt] ... slot 86 CreateGraphicsPipelineStateX ... desc:`) so the console description layout can be decoded.
State: the game thread runs its frame loop (WaitFrameEventX, command lists recorded, PresentX window created) and then dereferences
state the title builds from those pipelines (FUN_140b5a5d0, PSO-cache key hash, null `*param_1`). 11 of the 29 FidelityFX programs do
not translate (llvm-mc desyncs inside the code: Series X-specific encodings), so slot 67 fails for ~25 variants; harmless so far.
Still no frame, no loading screen.

---
## Assessment 2026-11-23 (end of session): what blocks a first frame
Slot 86 is called from FUN_142479760 (the title's own PSO-cache builder: it hashes ~0x2b0 bytes of render state, looks the key up in
its pipeline cache and otherwise asks the device). Turning that console description into a Vulkan graphics pipeline, plus the draw
side (DrawInstanced/ExecuteIndirect/DispatchMesh recording, render-pass handling), is what the upstream project tracks as open
(graphics pipelines, #291; docs/design.md and docs/pipeline_check.md say draw correctness is not checked yet). Without it nothing
can be drawn, including a loading screen. Also still missing for correct output: GPU-visible title memory (slots 70/133/74 are
stand-ins), 11 FidelityFX programs the disassembler cannot decode, mesh-compute and 32-wide-subgroup handling at run time on the RX 580.

---
## Update 2026-11-23 (night 2): graphics pipelines now create; the game then writes GPU packets itself
Decoded: slot 86 is `CreatePipelineStateX(const D3D12_PIPELINE_STATE_STREAM_DESC*, ID3D12PipelineState IID, out)`: {size 0x2b0, pStream},
the stream is the PC subobject layout (types 0/1/2/3/4/5/8/9/10/21/17/12/14/15/16, offline-parsed exactly to 0x2b0). It is now forwarded to
Device2::CreatePipelineState (real implementation, no stand-in). Shader bytecode in the streams is the DXBC-wrapped container; ten VS/PS
containers live in the executable's own .data (carved with carve_dll.py, stages from PSV0: stage byte 1 = VS, 0 = PS; staged under
`work/shaders/exe/dxbc` with an index.json giving the stage, translated into `spirv/exe/`; the library loads `<dir>/exe/`). A8_UNORM
render targets map to R8 in graphics pipelines. DirectStorage zlib requests are implemented (leonida::zlib_inflate); BCPack, swizzle and
physical-page requests are still E_NOTIMPL. With these, the first pipelines are created (calls 1..N ok).
New blocker, measured: the title's draw-state flush (FUN_140032520) does not call D3D12 draw methods. It appends packets with headers such
as 0xc000b600 into the command list's own buffer (a writer object reached through ctx+0x127c8 with write pointer [3] and end [6] and an
overflow virtual at +0xa0) and reads the "current program" from ctx+0x12328; with no program bound it dereferences null (FUN_140b5a5d0).
So drawing needs the console's direct command-buffer interface (list slots 74/126/146 etc.) to be modelled, i.e. a decoder for that packet
stream into Vulkan commands - not present upstream either. No frame is drawn.

---
## Update 2026-11-23 (night 3): what the first draw needs
The title's built-in program table (globals at image+0x1475d59c0.., filled by FUN_1419f4df0 via FUN_141d65750) is fully populated at the
crash, so the shader library loads (shaders.rpf is opened, DirectStorage requests succeed, no failed file opens). The crash is in the draw
flush FUN_140032520 reading `ctx+0x12328` (current program) == 0: the per-thread draw context (TLS +0x12a8, class with the PM4-like packet
writer at +0x127c8 and GPU-wait counter at +0x12198) was never put through its program-setting call (FUN_140122630 picks one of the built-in
programs by render-target format) before a draw was issued from job FUN_144fd1b20. Next step: trace the context's creation/reset path
(callers of FUN_140188430 and the code that runs at list Begin) to see which console call returns something this layer fakes.

### Draw-context trace (continued)
FUN_140b39840(blob, 0xf, 0) is the pass-begin's shader-program/state binder (it writes ctx+0x12328 only on some switch cases, `default:` skips);
the slot-index tables it reads (image+0x1476667c0..) and the built-in program table are populated at the crash, so the library side is fine.
The draw reaches FUN_140032520 with ctx+0x12328 == 0 because the program-selecting branch (FUN_140122630, reached from FUN_1401209b0, the only
caller, which takes a bound render-target array at ctx+0x12640) never ran: no render target was bound on this thread's context. Next: find
what binds ctx+0x12640[] (the SetRenderTargets equivalent) and why it is skipped (likely a back-buffer/swap-chain object this layer does not hand out).

---
## Update 2026-11-23 (night 4): launcher and where the draw's missing program comes from
- **Launching:** `gta6rt.exe` started with no arguments (double-click) now runs the title with built-in defaults (env defaults for D3D12=vulkan,
  shaders dir, pc-tail UBO, watchdog pause; image `D:\tools\work\exe\game_scarlett_master.exe`, game dir the dump). It is a console-subsystem
  program, so the log shows in its own window and the window closes when the process ends. Any argument or environment variable overrides.
- **Diagnostics added** (all opt-in by env): `LEONIDA_BP=addr,...` (int3 call logger), `LEONIDA_WATCH_LIB=1` (guard page on the program array),
  `LEONIDA_HACK_PROGRAM=1`, `LEONIDA_WAIT_LOADS=1`, `LEONIDA_SAMPLE_THREADS=n`, plus crash dumps (draw context, program library, RT globals).
- **Finding:** the draw's program comes from `lib[0xc78][idx]` (library object `*(image+0x1476667b8)`), which is never written: the
  title's init is a *task graph* (329 `FUN_141bb1cf0(fn, hash, flag)` registrations by FUN_14589f0e0 and friends, completion markers via
  FUN_141bb1b60 -> FUN_142225ef0). None of the registered task bodies (e.g. the state/program registration FUN_1457870f0 via
  FUN_1457780e0) ever runs although every pool worker is idle (waiting at FUN_14221c1f0), so the work-queue wake-up path is the next suspect.
  DirectStorage streaming itself is fine now (4200 zlib requests of shaders.rpf executed, 0 pending).
