import xml.etree.ElementTree as ET, os, sys
os.chdir(sys.argv[1])
lay = 'layout_3202719e-b4b4-421c-9f8f-70d1c4a7d60b_xs.xml'
t = ET.parse(lay); tot = 0; miss = []
for c in t.getroot():
    for fg in c:
        p = os.path.join(fg.get('DestinationPath').strip('\\').replace('\\', '/'), fg.get('Include')); tot += 1
        if not os.path.exists(p): miss.append((c.get('Id'), p))
print('listed', tot, 'missing', miss)
txt = open(lay).read()
print('top-level files not in layout:', [f for f in os.listdir('.') if os.path.isfile(f) and f not in txt])
# gameconfig.bin hive strings
b = open('microsoft_gameconfig.bin','rb').read()
import re
print('gameconfig utf16 strings:', [s.decode('utf-16le') for s in re.findall(rb'(?:[\x20-\x7e]\x00){4,}', b)][:40])
print('gameconfig ascii strings:', [s.decode() for s in re.findall(rb'[\x20-\x7e]{5,}', b)][:40])
