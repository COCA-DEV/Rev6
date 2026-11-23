import os, struct, sys
dll, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
b = open(dll, 'rb').read()
i = 0; n = 0; seen = set()
while True:
    i = b.find(b'DXBC', i)
    if i < 0: break
    if i + 32 <= len(b):
        ver_major, ver_minor, total, parts = struct.unpack_from('<HHII', b, i + 20)
        if 32 <= total <= 8 * 1024 * 1024 and i + total <= len(b) and parts < 64:
            blob = b[i:i + total]
            h = blob[4:20].hex()
            if h not in seen:
                seen.add(h)
                open(os.path.join(out, f'bvh_CS_{n:03d}_{h[:8]}_Wrapped.dxbc'), 'wb').write(blob)
                n += 1
            i += total
            continue
    i += 4
print('carved', n, 'containers from', os.path.basename(dll))

