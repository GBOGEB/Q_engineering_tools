#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,io,json,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
VOLATILE_CORE_TAGS={"{http://purl.org/dc/terms/}created","{http://purl.org/dc/terms/}modified","{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy","{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}revision"}
def h(b):return hashlib.sha256(b).hexdigest()
def normalize_xml(name,data):
 if name=='docProps/core.xml':
  root=ET.fromstring(data)
  for child in list(root):
   if child.tag in VOLATILE_CORE_TAGS: root.remove(child)
  data=ET.tostring(root,encoding='utf-8',xml_declaration=False)
 try:
  out=io.StringIO(); ET.canonicalize(xml_data=data.decode('utf-8'),out=out,with_comments=False); return out.getvalue().encode()
 except (UnicodeDecodeError,ET.ParseError): return data
def manifest(path):
 rows=[]
 with zipfile.ZipFile(path) as z:
  for name in sorted(n for n in z.namelist() if not n.endswith('/')):
   data=z.read(name)
   if name.endswith('.xml') or name.endswith('.rels'): data=normalize_xml(name,data)
   rows.append({'part':name,'normalized_sha256':h(data),'size':len(data)})
 canonical=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
 return {'raw_sha256':h(path.read_bytes()),'normalized_release_sha256':h(canonical),'part_count':len(rows),'identity_semantics':'NORMALIZED_RELEASE_EQUIVALENCE_NOT_RAW_BYTE_IDENTITY'}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('paths',nargs='+',type=Path); ap.add_argument('--receipt',type=Path); a=ap.parse_args(); r={str(p):manifest(p) for p in a.paths};
 if a.receipt:a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
 print(json.dumps(r,sort_keys=True))
if __name__=='__main__':main()
