"""Two newly proved ex-dividend notices only; reuse Stage6 safe transport.

No list queries, no previous Stage6 document and no repeat attempt. Stops on the
first DART/HTTP/identity error. Source metadata must match the preserved replies.
"""
import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stage6_documents", ROOT / "docs/audits/version-pit-stage6-20261014/collect_documents.py")
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
RECEIPTS = ("20191226900748", "20201228900943")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    home = ROOT / "docs/research/stage12-stock-dividend-20261016/official_metadata"
    state = json.loads((home / "state.json").read_text())
    catalog = {}
    for response in state["responses"]:
        raw = (home / response["file"]).read_bytes()
        assert len(raw) == response["bytes"] and hashlib.sha256(raw).hexdigest() == response["sha256"]
        catalog.update({r["rcept_no"]: r for r in json.loads(raw)["list"]})
    rows = []
    for receipt in RECEIPTS:
        row = catalog[receipt]
        assert row["corp_code"] == "00554024" and row["stock_code"] == "091990"
        assert row["report_nm"] == "배당락(주식배당)"
        rows.append({"rcept_no": receipt, "corp_code": row["corp_code"], "report_nm": row["report_nm"]})
    result = original.acquire(rows, os.environ.get("DART_API_KEY", ""), args.output)
    # Emit only safe post-validation evidence. Exclude any DART error XML body;
    # its HTTP/status/SHA remains in state. No requests/keys or exception URLs.
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in ["run_state.json", "response_manifest.json"]:
            z.writestr(name, (args.output / name).read_bytes())
        for response in result["responses"]:
            if response["kind"] == "ZIP":
                z.writestr(response["file"], (args.output / response["file"]).read_bytes())
    raw = bundle.getvalue()
    if len(raw) > 256 * 1024:
        print("BOUNDED_BUNDLE_EXCEEDS_LOG_TRANSFER; artifact retained")
    else:
        print("STAGE12_DOCUMENT_BUNDLE_BASE64_BEGIN")
        text = base64.b64encode(raw).decode("ascii")
        for offset in range(0, len(text), 2000):
            print(text[offset:offset + 2000])
        print("STAGE12_DOCUMENT_BUNDLE_BASE64_END")
        print(json.dumps({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}))
    print(json.dumps({"status": result["status"], "requests": result["requests"], "error": result.get("error")}))
    return 0 if result["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
