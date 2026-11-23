import ctypes, sys, os
from ctypes import wintypes
exe = sys.argv[1]
rvas = [int(x, 16) for x in sys.argv[2:]]
dh = ctypes.WinDLL('dbghelp.dll')
dh.SymInitialize.argtypes = [wintypes.HANDLE, wintypes.LPCSTR, wintypes.BOOL]
dh.SymLoadModuleEx.restype = ctypes.c_uint64
dh.SymLoadModuleEx.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPCSTR, wintypes.LPCSTR, ctypes.c_uint64, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
h = ctypes.c_void_p(1)
dh.SymSetOptions(0x2 | 0x4 | 0x10000000)  # UNDNAME | DEFERRED | (LOAD_LINES off)
assert dh.SymInitialize(h, os.path.dirname(exe).encode(), False)
base = 0x10000000
b = dh.SymLoadModuleEx(h, None, exe.encode(), None, base, os.path.getsize(exe), None, 0)
print('loaded base', hex(b))
class SYM(ctypes.Structure):
    _fields_ = [('SizeOfStruct', wintypes.ULONG), ('TypeIndex', wintypes.ULONG), ('Reserved', ctypes.c_uint64 * 2), ('Index', wintypes.ULONG),
                ('Size', wintypes.ULONG), ('ModBase', ctypes.c_uint64), ('Flags', wintypes.ULONG), ('Value', ctypes.c_uint64),
                ('Address', ctypes.c_uint64), ('Register', wintypes.ULONG), ('Scope', wintypes.ULONG), ('Tag', wintypes.ULONG),
                ('NameLen', wintypes.ULONG), ('MaxNameLen', wintypes.ULONG), ('Name', ctypes.c_char * 512)]
for r in rvas:
    s = SYM(); s.SizeOfStruct = 88; s.MaxNameLen = 512
    disp = ctypes.c_uint64(0)
    ok = dh.SymFromAddr(h, base + r, ctypes.byref(disp), ctypes.byref(s))
    print(hex(r), s.Name.decode(errors='replace') + ' +0x%x' % disp.value if ok else 'no symbol')
