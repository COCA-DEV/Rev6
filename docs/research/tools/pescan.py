import pefile, sys, os, json, datetime
root = sys.argv[1]
files = [f for f in sorted(os.listdir(root)) if f.lower().endswith(('.dll','.exe','.bin'))]
out = {}
for f in files:
    p = os.path.join(root, f)
    with open(p,'rb') as fh:
        if fh.read(2) != b'MZ': continue
    d = {'size': os.path.getsize(p)}
    try:
        pe = pefile.PE(p, fast_load=False)
    except Exception as e:
        d['error'] = str(e); out[f]=d; continue
    fh_ = pe.FILE_HEADER; oh = pe.OPTIONAL_HEADER
    d['machine'] = hex(fh_.Machine); d['nsections']=fh_.NumberOfSections
    d['timestamp'] = datetime.datetime.utcfromtimestamp(fh_.TimeDateStamp).isoformat()
    d['characteristics'] = hex(fh_.Characteristics)
    d['magic'] = hex(oh.Magic); d['entry']=hex(oh.AddressOfEntryPoint); d['imagebase']=hex(oh.ImageBase)
    d['subsystem']=oh.Subsystem; d['osver']=f"{oh.MajorOperatingSystemVersion}.{oh.MinorOperatingSystemVersion}"
    d['subsysver']=f"{oh.MajorSubsystemVersion}.{oh.MinorSubsystemVersion}"
    d['linker']=f"{oh.MajorLinkerVersion}.{oh.MinorLinkerVersion}"
    d['dllchar']=hex(oh.DllCharacteristics); d['sizeofimage']=hex(oh.SizeOfImage)
    d['checksum']=hex(oh.CheckSum)
    d['sections']=[(s.Name.rstrip(b'\0').decode(errors='replace'),hex(s.VirtualAddress),hex(s.Misc_VirtualSize),hex(s.PointerToRawData),hex(s.SizeOfRawData),hex(s.Characteristics)) for s in pe.sections]
    dd = {}
    for i,e in enumerate(oh.DATA_DIRECTORY):
        if e.VirtualAddress or e.Size: dd[e.name]=(hex(e.VirtualAddress),hex(e.Size))
    d['datadirs']=dd
    imps = {}
    for ent in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]):
        imps[ent.dll.decode()] = [ (i.name.decode() if i.name else f"ord{i.ordinal}") for i in ent.imports]
    d['imports']=imps
    dimps = {}
    for ent in getattr(pe,'DIRECTORY_ENTRY_DELAY_IMPORT',[]):
        dimps[ent.dll.decode()] = [ (i.name.decode() if i.name else f"ord{i.ordinal}") for i in ent.imports]
    d['delayimports']=dimps
    exps = []
    if hasattr(pe,'DIRECTORY_ENTRY_EXPORT'):
        d['export_name']=pe.DIRECTORY_ENTRY_EXPORT.name.decode(errors='replace') if pe.DIRECTORY_ENTRY_EXPORT.name else None
        for s in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            exps.append((s.ordinal, s.name.decode() if s.name else None, hex(s.address)))
    d['exports']=exps
    dbg=[]
    for e in getattr(pe,'DIRECTORY_ENTRY_DEBUG',[]):
        if e.entry is not None and hasattr(e.entry,'PdbFileName'):
            dbg.append(e.entry.PdbFileName.rstrip(b'\0').decode(errors='replace'))
        else: dbg.append(f"type{e.struct.Type}")
    d['debug']=dbg
    if hasattr(pe,'DIRECTORY_ENTRY_TLS'):
        t=pe.DIRECTORY_ENTRY_TLS.struct
        d['tls']=hex(t.AddressOfCallBacks)
    ver={}
    for fi in getattr(pe,'FileInfo',[]) or []:
        for e in fi:
            if hasattr(e,'StringTable'):
                for st in e.StringTable:
                    for k,v in st.entries.items(): ver[k.decode(errors='replace')]=v.decode(errors='replace')
    d['version']=ver
    out[f]=d
json.dump(out, open(sys.argv[2],'w'), indent=1)
print(len(out),'PE files')
