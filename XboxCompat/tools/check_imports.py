"""Static import check: which imports of the dump's DLLs are still unresolved once the XboxCompat shims exist?

Nothing from the dump is loaded or executed. Inputs:
  argv[1]  pe.json produced by docs/research/tools/pescan.py
  argv[2]  directory holding the built shim DLLs (XboxCompat/build/bin)
Resolution order per imported DLL: dump-bundled DLL -> shim DLL (export table parsed with pefile) -> Windows System32
(LoadLibraryEx with LOAD_LIBRARY_SEARCH_SYSTEM32 + GetProcAddress of Windows' own DLLs only).
Run with: python -I check_imports.py <pe.json> <shim_dir>
"""
import ctypes, json, os, sys
from ctypes import wintypes
import pefile

pe_json, shim_dir = sys.argv[1], sys.argv[2]
d = json.load(open(pe_json))
bundled = {f.lower() for f in d}

shim_exports = {}
for f in os.listdir(shim_dir):
    if f.lower().endswith('.dll'):
        pe = pefile.PE(os.path.join(shim_dir, f), fast_load=False)
        names = {s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
        shim_exports[f.lower()] = names

k = ctypes.WinDLL('kernel32', use_last_error=True)
k.LoadLibraryExW.restype = wintypes.HMODULE
k.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
k.GetProcAddress.restype = ctypes.c_void_p
k.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_char_p]

unresolved = {}
via_shim = {}
for image, v in sorted(d.items()):
    for dll, funcs in v.get('imports', {}).items():
        key = dll.lower()
        if key in bundled:
            continue
        if key in shim_exports:
            for fn in funcs:
                if fn.startswith('ord') or fn not in shim_exports[key]:
                    unresolved.setdefault((image, dll), []).append(fn)
                else:
                    via_shim.setdefault((image, dll), []).append(fn)
            continue
        h = k.LoadLibraryExW(dll, None, 0x800)
        if not h:
            unresolved.setdefault((image, dll), []).extend(funcs)
            continue
        for fn in funcs:
            if fn.startswith('ord'):
                continue  # ordinal imports checked separately (XAudio2_9 ord 1 verified in research)
            if not k.GetProcAddress(h, fn.encode()):
                unresolved.setdefault((image, dll), []).append(fn)

print('Resolved through XboxCompat shims:')
for (image, dll), fns in sorted(via_shim.items()):
    print(f'  {image:36} {dll:14} {sorted(fns)}')
print('\nStill unresolved:')
if not unresolved:
    print('  (none among the present DLLs)')
for (image, dll), fns in sorted(unresolved.items()):
    print(f'  {image:36} {dll:14} {sorted(fns)}')
print('\nNOTE: the game executable is not in the dump, so its own imports are NOT covered by this check.')
sys.exit(1 if unresolved else 0)
