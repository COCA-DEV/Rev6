import os, sys, struct, math, collections, re
root = sys.argv[1]
def ent(b):
    if not b: return 0
    c = collections.Counter(b); n=len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())
def rd(p, off, n):
    with open(p,'rb') as f:
        f.seek(off); return f.read(n)
# XVD
p = os.path.join(root,'gameos.xvd'); sz=os.path.getsize(p)
h = rd(p,0,0x1000)
print('XVD size',sz, 'magic@0x200', h[0x200:0x208])
vf, fv = struct.unpack_from('<II', h, 0x208)
ft, ds = struct.unpack_from('<QQ', h, 0x210)
print('volume_flags',hex(vf),'format_version',fv,'drive_size',ds,hex(ds),'(file size %d)'%sz)
print('content_id', h[0x220:0x230].hex())
xt, ct, emb, ud, xvcl, dyn, bs = struct.unpack_from('<IIIIIII', h, 0x280) if False else (0,)*7
print('hdr entropy[0:0x200]',round(ent(h[:0x200]),2),'[0x200:0x1000]',round(ent(h[0x200:]),2))
for off in (0x1000, 0x10000, 0x100000, 0x1000000):
    print(' entropy @',hex(off), round(ent(rd(p,off,65536)),3))
# search readable markers in gameos.xvd (first 64MB) — just report whether plain PE headers appear
data = rd(p, 0, 64*1024*1024)
print('MZ occurrences in first 64MB of xvd:', data.count(b'MZ\x90\x00'))
print('game_scarlett in xvd(64MB):', data.count(b'game_scarlett'))
# catalog
c = open(os.path.join(root,'Catalog000.bin'),'rb').read()
print('Catalog entropy first 64K',round(ent(c[0x1000:0x11000]),3),'strings game_scarlett:',c.count(b'game_scarlett'), 'ascii_dll names:', set(re.findall(rb'[A-Za-z0-9_\-\.]{4,40}\.(?:dll|exe)', c)))
print('catalog hdr',c[:0x40].hex(), 'peoff', struct.unpack_from('<I',c,0x3c))
# RPF / TTPF
for dp, dn, fn in os.walk(root):
    for f in sorted(fn):
        if f.lower().endswith(('.rpf','.ttpf')):
            q=os.path.join(dp,f); b=rd(q,0,0x10000)
            hd = struct.unpack_from('<8I', b, 0)
            print(os.path.relpath(q,root), os.path.getsize(q), 'hdr', [hex(x) for x in hd[:6]], 'ent[0:64K]', round(ent(b),2), 'ent[0x40:0x1000]', round(ent(b[0x40:0x1000]),2))
