"""Bounded UTF8 log transport of read-only evidence; never API credentials."""
import base64,hashlib,io,json,zipfile

def emit(out,label):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(out.rglob('*')):
   if p.is_file():z.writestr(str(p.relative_to(out)),p.read_bytes())
 raw=b.getvalue()
 if len(raw)>5*1024*1024:raise ValueError('Evidence transport exceeds5MiB; original artifact preserved')
 print(label+'_BEGIN',flush=True);s=base64.b64encode(raw).decode()
 for i in range(0,len(s),2000):print(s[i:i+2000],flush=True)
 print(label+'_END',flush=True);print(json.dumps(dict(label=label,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())),flush=True)
