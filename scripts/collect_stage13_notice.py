"""One previously unrequested, metadata-proved notice. No price/list calls.

The financial-document identity validator is deliberately NOT relaxed. Safe
identity-rejected bytes are quarantined for format diagnosis, not certified.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile
from collect_stock_dividend_documents import original, fetch_and_quarantine, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    receipt = "20201228900943"  # Stage12 stopped before requesting this receipt.
    home = ROOT / "docs/research/stage12-stock-dividend-20261016/official_metadata"
    state = json.loads((home / "state.json").read_text())
    pin = next(r for r in state["responses"] if r["file"] == "091990_page1.json")
    raw = (home / pin["file"]).read_bytes()
    assert len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"]
    row = next(r for r in json.loads(raw)["list"] if r["rcept_no"] == receipt)
    assert row["corp_code"] == "00554024" and row["stock_code"] == "091990" and row["report_nm"] == "배당락(주식배당)"
    result = original.acquire([row], os.environ.get("DART_API_KEY", ""), a.output,
        transport=lambda r,k: fetch_and_quarantine(r,k,a.output,"00554024"))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(a.output.rglob("*")):
            if p.is_file():
                z.writestr(str(p.relative_to(a.output)),p.read_bytes())
    bundle = stream.getvalue()
    if len(bundle) <= 256*1024:
        print("STAGE13_SAFE_NOTICE_BEGIN")
        encoded=base64.b64encode(bundle).decode()
        for offset in range(0,len(encoded),2000): print(encoded[offset:offset+2000])
        print("STAGE13_SAFE_NOTICE_END")
        print(json.dumps(dict(bytes=len(bundle),sha256=hashlib.sha256(bundle).hexdigest())))
    print(json.dumps(dict(status=result["status"],requests=result["requests"],error=result.get("error"))))
    return 0 if result["status"]=="COMPLETE" else 2


if __name__=="__main__": raise SystemExit(main())
