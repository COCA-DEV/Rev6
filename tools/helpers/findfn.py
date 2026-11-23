import struct, sys, bisect
exe = r'D:\tools\work\exe\game_scarlett_master.exe'
PD_RVA, PD_SIZE = 0xabcf000, 0x36cbac
# .pdata section: VA 0xabcf000 raw 0x6e03a00 (from the section table)
RAW, VA = 0x6e03a00, 0xabcf000
f = open(exe, 'rb')
f.seek(RAW + (PD_RVA - VA)); data = f.read(PD_SIZE)
n = len(data) // 12
begins = [struct.unpack_from('<I', data, i * 12)[0] for i in range(n)]
ends = [struct.unpack_from('<I', data, i * 12 + 4)[0] for i in range(n)]
def find(rva):
    i = bisect.bisect_right(begins, rva) - 1
    if i >= 0 and begins[i] <= rva < ends[i]: return begins[i], ends[i]
    return None
for a in sys.argv[1:]:
    r = int(a, 16); fn = find(r)
    print(hex(r), '->', ('start 0x%x end 0x%x (VA 0x%x)' % (fn[0], fn[1], 0x140000000 + fn[0])) if fn else 'not in .pdata')
