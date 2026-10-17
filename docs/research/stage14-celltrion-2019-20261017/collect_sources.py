"""Bounded new primary-source evidence only; never prices or operational data.

One metadata-proved CT2019 proposal for record/fraction terms (not previously
requested by the Stage12/13 document jobs), and issuer archive + at most three
same-origin page scripts for discovering its public historical search route.
HTML is preserved as HTML, not forced through an annual-report XML parser.
"""
import argparse
import base64
import hashlib
from html import unescape
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
from urllib import request, error, parse
import zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
s=importlib.util.spec_from_file_location("frozen_safe_source",ROOT/"docs/audits/version-pit-stage6-20261014/collect_documents.py")
safe=importlib.util.module_from_spec(s);s.loader.exec_module(safe)
MAX_BYTES=2*1024*1024


class Text(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True);self.text=[];self.scripts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="script" and a.get("src"): self.scripts.append(a["src"])
        if tag in {"script","style"}: self.skip+=1
        if tag in {"tr","td","th","p","br"}: self.text.append("\n" if tag in {"tr","p","br"} else " | ")
    def handle_endtag(self,tag):
        if tag in {"script","style"}: self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip: self.text.append(data)


def inspect_archive(payload,key):
    if len(payload)>safe.MAX_BYTES: raise ValueError("RESPONSE_SIZE_LIMIT")
    if key and key.encode() in payload: raise ValueError("CREDENTIAL_ECHO_BLOCKED")
    if not zipfile.is_zipfile(io.BytesIO(payload)): raise ValueError("NOT_DOCUMENT_ARCHIVE")
    members=[];texts={}
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        if len(z.infolist())>100 or sum(i.file_size for i in z.infolist())>safe.MAX_EXPANDED: raise ValueError("ARCHIVE_EXPANSION_LIMIT")
        if z.testzip() is not None: raise ValueError("ARCHIVE_CRC_FAILURE")
        # Every member is scanned before ANY raw archive is retained.
        for i in z.infolist():
            p=PurePosixPath(i.filename)
            if p.is_absolute() or ".." in p.parts: raise ValueError("UNSAFE_MEMBER_PATH")
            if i.is_dir(): continue
            raw=z.read(i);text=safe.decode(raw)
            if key:
                safe.echo_check(raw,key)
                if key in unescape(text): raise ValueError("CREDENTIAL_ECHO_BLOCKED")
            html=bool(re.search(r"<!DOCTYPE\s+HTML|<html\b",text,re.I))
            xml_error=None
            try: ET.fromstring(text);xml=True
            except ET.ParseError as e: xml=False;xml_error=str(e)[:120]
            parser=Text();parser.feed(text)
            texts[i.filename]="".join(parser.text)
            members.append(dict(name=i.filename,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                                format="HTML" if html else "XML" if xml else "UNVERIFIED_TEXT",strict_xml_valid=xml,strict_xml_error=xml_error))
    return members,texts


def fetch(url):
    try:
        with request.build_opener(safe.NoRedirect()).open(request.Request(url),timeout=25) as r:
            raw=r.read(safe.MAX_BYTES+1)
            return r.status,r.headers.get("Content-Type",""),raw
    except error.HTTPError as e: raise safe.Stop("HTTP_FAILURE",e.code) from None
    except safe.Stop: raise
    except Exception: raise safe.Stop("TRANSPORT_FAILURE") from None


def issuer_history(output):
    """UI-proved GET form, max3 result pages + max2 relevant2020 notices."""
    output.mkdir(parents=True,exist_ok=False)
    base="https://www.celltrion.com/ko-kr/investment/notice/announce"
    state=dict(requests=0,retries=0,responses=[],entries=[],errors=[],investment_approved=False)
    selected=[]
    try:
        for page in range(1,4):
            url=base+"?"+parse.urlencode(dict(page=page,searchWord="배당",selectType=""))
            state["requests"]+=1
            http,ct,raw=fetch(url)
            if len(raw)>MAX_BYTES: raise ValueError("RESPONSE_SIZE_LIMIT")
            text=raw.decode("utf-8")
            (output/f"search_{page}.html").write_bytes(raw)
            state["responses"].append(dict(url=url,http=http,content_type=ct,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            matches=re.findall(r'no="(\d+)"[^>]*>\s*<p class="subject">(.*?)</p>\s*<span class="date">([\d.]+)</span>',text,re.S)
            entries=[]
            for ident,title,date in matches:
                title=unescape(re.sub("<[^>]+>","",title)).strip()
                entry=dict(id=ident,title=title,date=date,url=base+"/"+ident)
                entries.append(entry)
                if date.startswith("2020.") and re.search("배당",title): selected.append(entry)
            state["entries"].extend(entries)
            if selected or not entries or min(e["date"] for e in entries)<"2020.01.01": break
        for entry in selected[:2]:
            state["requests"]+=1
            http,ct,raw=fetch(entry["url"])
            if len(raw)>MAX_BYTES: raise ValueError("RESPONSE_SIZE_LIMIT")
            text=raw.decode("utf-8");parser=Text();parser.feed(text)
            (output/(entry["id"]+".html")).write_bytes(raw)
            (output/(entry["id"]+"_text.txt")).write_text("".join(parser.text))
            state["responses"].append(dict(**entry,http=http,content_type=ct,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    except (safe.Stop,ValueError,UnicodeError) as e:
        state["errors"].append(dict(reason=e.kind if isinstance(e,safe.Stop) else type(e).__name__,http=getattr(e,"http",None)))
    (output/"state.json").write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n")
    emit_bundle(output,state)
    return int(bool(state["errors"]))


def emit_bundle(output,state):
    bundle=io.BytesIO()
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(output.iterdir()): z.writestr(f.name,f.read_bytes())
    raw=bundle.getvalue()
    if len(raw)<=256*1024:
        print("STAGE14_SOURCE_BUNDLE_BEGIN")
        encoded=base64.b64encode(raw).decode()
        for i in range(0,len(encoded),2000): print(encoded[i:i+2000])
        print("STAGE14_SOURCE_BUNDLE_END")
    print(json.dumps(dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),requests=state["requests"],errors=state["errors"])))


def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--issuer-history",action="store_true");a=p.parse_args()
    if a.issuer_history: return issuer_history(a.output)
    a.output.mkdir(parents=True,exist_ok=False)
    state=dict(requests=0,retries=0,responses=[],errors=[],investment_approved=False)
    key=os.environ.get("DART_API_KEY","")
    receipt="20191218800434"
    metadata=ROOT/"docs/research/stage12-stock-dividend-20261016/official_metadata/068270_page1.json"
    assert hashlib.sha256(metadata.read_bytes()).hexdigest()=="4840d8b16244264f874986c41ec4671af6fb321033e3a9453cd704a2a4880289"
    row=next(r for r in json.loads(metadata.read_bytes())["list"] if r["rcept_no"]==receipt)
    assert row["corp_code"]=="00413046" and row["stock_code"]=="068270" and row["report_nm"]=="주식배당결정"
    if not re.fullmatch(r"[A-Za-z0-9]{40}",key): state["errors"].append(dict(scope="dart",reason="AUTH_ENV_MISSING_OR_INVALID"))
    else:
        state["requests"]+=1
        try:
            url="https://opendart.fss.or.kr/api/document.xml?"+parse.urlencode(dict(rcept_no=receipt,crtfc_key=key))
            http,content_type,raw=fetch(url)
            members,texts=inspect_archive(raw,key)
            (a.output/(receipt+".zip")).write_bytes(raw)
            (a.output/(receipt+"_text.json")).write_text(json.dumps(texts,ensure_ascii=False,indent=2)+"\n")
            state["responses"].append(dict(source="OpenDART document.xml",receipt=receipt,http=http,content_type=content_type,
                bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),members=members,identity="UNVERIFIED pending independent text review"))
        except (safe.Stop,ValueError) as e:
            state["errors"].append(dict(scope="dart",reason=e.kind if isinstance(e,safe.Stop) else str(e),http=getattr(e,"http",None)))
    archive="https://www.celltrion.com/ko-kr/investment/notice/announce"
    queue=[archive]
    for index in range(4):
        if index>=len(queue): break
        url=queue[index];state["requests"]+=1
        try:
            http,content_type,raw=fetch(url)
            if len(raw)>MAX_BYTES: raise ValueError("RESPONSE_SIZE_LIMIT")
            text=raw.decode("utf-8")
            if key and key in unescape(text): raise ValueError("CREDENTIAL_ECHO_BLOCKED")
            (a.output/f"issuer_{index}.txt").write_bytes(raw)
            parser=Text();parser.feed(text)
            state["responses"].append(dict(source=url,http=http,content_type=content_type,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                scripts=parser.scripts,snippets=[text[max(0,m.start()-180):m.start()+600] for m in list(re.finditer(r"/api/|announce|searchKeyword|currentPage",text))[:14]]))
            if index==0:
                candidates=[parse.urljoin(archive,src) for src in parser.scripts if re.search(r"page|announce|investment|common|main|app",src,re.I)]
                queue.extend([u for u in candidates if parse.urlparse(u).netloc=="www.celltrion.com"][-3:])
        except (safe.Stop,ValueError,UnicodeError) as e:
            state["errors"].append(dict(scope="issuer",source=url,reason=e.kind if isinstance(e,safe.Stop) else type(e).__name__,http=getattr(e,"http",None)))
            break  # no repeated failing host/path
    (a.output/"state.json").write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n")
    emit_bundle(a.output,state)
    return int(bool(state["errors"]))


if __name__=="__main__": raise SystemExit(main())
