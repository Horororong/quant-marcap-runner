"""Read-only preservation checks; never parses or reprocesses financial sources."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

HOME = Path(__file__).resolve().parent
ROOT = HOME.parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--originals", type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    expected = json.loads((HOME / "preservation_manifest.json").read_text())
    result = {"status": "FAIL", "scope": "byte preservation, not financial recertification",
              "checked_files": 0, "original60": "UNVERIFIED", "protected518": "UNVERIFIED", "core64": "UNVERIFIED"}
    try:
        for name, pin in expected["files"].items():
            raw = (ROOT / name).read_bytes()
            assert len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"], name
            result["checked_files"] += 1
        delivery = json.loads((HOME / "artifact_manifest.json").read_text())["files"]
        for name, pin in delivery.items():
            raw = (HOME / name).read_bytes()
            assert len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"], name
        result["stage12_artifact_files"] = len(delivery)
        for name, sha in json.loads((HOME / "implementation_sha256.json").read_text()).items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
        financial = ROOT / "docs/audits/financial-extraction-stage3-20261014/results"
        with (financial / "protected518.csv").open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 518 and all(r["verdict"] == r["new_independent_field_verdict"] == "PASS" and r["before_value"] == r["after_value"] for r in rows)
        assert json.loads((financial / "validation_summary.json").read_text())["holdout64_targets"] == {"PASS": 64, "FAIL": 0, "UNVERIFIED": 0}
        result.update(protected518="PASS_PRESERVED", core64="PASS_PRESERVED")
        if a.originals:
            spec = importlib.util.spec_from_file_location("original60_verifier", ROOT / "docs/audits/version-pit-stage6-20261014/verify_preserved60.py")
            verifier = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(verifier)
            with zipfile.ZipFile(a.originals) as archive:
                assert verifier.verify_originals(archive) == 60
            result["original60"] = "PASS_PRESERVED_NESTED_MEMBERS"
            result["original60_archive_sha256"] = hashlib.sha256(a.originals.read_bytes()).hexdigest()
        result["status"] = "PASS_PRESERVATION_CONTROLS"
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    (a.output / "preservation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return int(result["status"] != "PASS_PRESERVATION_CONTROLS")


if __name__ == "__main__":
    raise SystemExit(main())
