"""Stage14: frozen financial/data/audit and unchanged engine bytes; no reprocessing."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

HOME=Path(__file__).resolve().parent
ROOT=HOME.parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True);parser.add_argument("--originals",type=Path)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    result=dict(status="FAIL",scope="preservation only, no financial/PIT recertification",checked_files=0,original60="UNVERIFIED")
    try:
        manifest=json.loads((HOME/"preservation_manifest.json").read_text())
        for name,pin in manifest["files"].items():
            raw=(ROOT/name).read_bytes()
            assert len(raw)==pin["bytes"] and hashlib.sha256(raw).hexdigest()==pin["sha256"],name
            result["checked_files"]+=1
        folder=ROOT/"docs/audits/financial-extraction-stage3-20261014/results"
        with (folder/"protected518.csv").open(encoding="utf-8-sig") as f: rows=list(csv.DictReader(f))
        assert len(rows)==518 and all(r["verdict"]==r["new_independent_field_verdict"]=="PASS" and r["before_value"]==r["after_value"] for r in rows)
        assert json.loads((folder/"validation_summary.json").read_text())["holdout64_targets"]==dict(PASS=64,FAIL=0,UNVERIFIED=0)
        result.update(protected518=518,core64=64)
        if a.originals:
            s=importlib.util.spec_from_file_location("frozen_originals_verifier",ROOT/"docs/audits/version-pit-stage6-20261014/verify_preserved60.py")
            m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
            with zipfile.ZipFile(a.originals) as z: assert m.verify_originals(z)==60
            result["original60"]="PASS_NESTED_MEMBERS"
        result["status"]="PASS_PRESERVED"
    except Exception as e:
        result["error"]=dict(type=type(e).__name__,message=str(e))
    (a.output/"preservation.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
    return int(result["status"]!="PASS_PRESERVED")


if __name__=="__main__": raise SystemExit(main())
