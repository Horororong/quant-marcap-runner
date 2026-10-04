"""Recheck the independent 72-cell audit against this checkout's actual data.

Sources are archived official bodies; expected cells and amount comparisons
are owned by the pre-existing independent audit, not by the collector/adapter.
No source request, financial repair, PIT promotion or checkpoint update occurs.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/legacy_dart"
MAX_SOURCE_BYTES = 2_000_000


def materialize_sources(destination):
    destination = Path(destination)
    evidence = []
    for item in json.loads((FIXTURES / "viewer_primary/manifest.json").read_text())["records"]:
        path = FIXTURES / "viewer_primary" / item["file"]
        packed = path.read_bytes()
        if path.name != item["file"] or hashlib.sha256(packed).hexdigest() != item["gzip_sha256"]:
            raise ValueError("viewer fixture SHA/path mismatch")
        with gzip.open(path, "rb") as stream:
            body = stream.read(MAX_SOURCE_BYTES + 1)
        cap = item["capture"]
        if len(body) != cap["body_bytes"] or len(body) > MAX_SOURCE_BYTES or hashlib.sha256(body).hexdigest() != cap["body_sha256"]:
            raise ValueError("viewer primary body mismatch")
        (destination / path.name.removesuffix(".gz")).write_bytes(body)
        evidence.append({"file": path.name.removesuffix(".gz"), "source_sha256": cap["body_sha256"], "artifact_id": item["artifact_id"]})
    for item in json.loads((FIXTURES / "native_primary/manifest.json").read_text())["records"]:
        path = FIXTURES / "native_primary" / item["file"]
        packed = path.read_bytes()
        if path.name != item["file"] or len(packed) != item["zip_bytes"] or hashlib.sha256(packed).hexdigest() != item["document_sha256"]:
            raise ValueError("native archive SHA/path mismatch")
        if Path(item["member_name"]).name != item["member_name"]:
            raise ValueError("native member path escape")
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(item["member_name"])
            if info.file_size != item["member_bytes"] or info.file_size > MAX_SOURCE_BYTES:
                raise ValueError("native member size mismatch")
            body = archive.read(info)
        if hashlib.sha256(body).hexdigest() != item["member_sha256"]:
            raise ValueError("native primary member SHA mismatch")
        body.decode(item["source_encoding"], errors="strict")
        (destination / item["member_name"]).write_bytes(body)
        evidence.append({"file": item["member_name"], "source_sha256": item["member_sha256"], "document_sha256": item["document_sha256"], "artifact_id": item["artifact_id"]})
    if len(evidence) != 14:
        raise ValueError("expected fourteen frozen primary bodies")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError("preserve earlier audit output; use a new output directory")
    repo = args.repo_root.resolve()
    paths = [repo / "data/financials/legacy_2000_2014/legacy_filings.csv.gz",
             repo / "data/status/dart_legacy_backfill_state.csv"]
    paths += sorted((repo / "data/financials/legacy_2000_2014/normalized").glob("*.csv.gz"))
    before = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with tempfile.TemporaryDirectory(prefix="legacy-primary-audit-") as directory:
        evidence = materialize_sources(directory)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        process = subprocess.run([sys.executable, str(ROOT / "docs/audits/data-readiness-20261004/verify_financial_samples.py"),
                                  "--repo-root", str(repo), "--source-dir", directory, "--output-dir", str(args.output_dir)],
                                 capture_output=True, text=True, timeout=45)
    after = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    log = {"returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr,
           "input_sha256": before, "inputs_unchanged": before == after, "primary_sources": evidence}
    (args.output_dir / "recheck_provenance.json").write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n")
    if process.returncode != 0 or before != after:
        raise RuntimeError("independent source audit failed or data changed during audit; evidence preserved")
    summary = json.loads((args.output_dir / "financial_summary.json").read_text())
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
