import json, ctypes, sys, os, pefile
from ctypes import wintypes
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.LoadLibraryExW.restype = wintypes.HMODULE
k.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
k.GetProcAddress.restype = ctypes.c_void_p
k.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_char_p]
d = json.load(open(sys.argv[1]))
bundled = {f.lower() for f in d}
res = {}
for f, v in d.items():
    for dll, funcs in v.get('imports', {}).items():
        res.setdefault(dll, {'importers': set(), 'funcs': set()})
        res[dll]['importers'].add(f); res[dll]['funcs'].update(funcs)
out = {}
for dll, r in sorted(res.items(), key=lambda x: x[0].lower()):
    if dll.lower() in bundled:
        out[dll] = ('BUNDLED_IN_DUMP', sorted(r['importers']), []); continue
    h = k.LoadLibraryExW(dll, None, 0x800)  # LOAD_LIBRARY_SEARCH_SYSTEM32
    if not h:
        out[dll] = ('NOT_ON_HOST', sorted(r['importers']), sorted(r['funcs'])); continue
    miss = [fn for fn in sorted(r['funcs']) if not fn.startswith('ord') and not k.GetProcAddress(h, fn.encode())]
    out[dll] = ('HOST_OK' if not miss else 'HOST_PARTIAL', sorted(r['importers']), miss)
for dll, (st, imp, miss) in out.items():
    print(f"{st:16} {dll:60} importers={len(imp)} missing={miss if st!='NOT_ON_HOST' else '(all)'}")
# XAudio2_9 ordinal 1 and host presence of xmem/d3d12_xs
for n in ('XAudio2_9.dll',):
    p = os.path.join(os.environ['SystemRoot'], 'System32', n)
    if os.path.exists(p):
        pe = pefile.PE(p, fast_load=False)
        print(n, [(s.ordinal, s.name) for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.ordinal == 1])
for n in ('xmem.dll','d3d12_xs.dll','d3d12.dll','dxgi.dll'):
    print(n, 'in System32:', os.path.exists(os.path.join(os.environ['SystemRoot'],'System32',n)))
