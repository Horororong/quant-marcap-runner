from __future__ import annotations

"""Standalone, standard-library-only offline kit bootstrap and integrity owner."""

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile

KIT_CONTRACT_VERSION = "1"
SUPPORTED_PYTHON = ("3.11", "3.12")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


class KitIntegrityError(ValueError):
    pass


class KitEnvironmentError(ValueError):
    pass


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_id(manifest):
    return hashlib.sha256(canonical_bytes({k: v for k, v in manifest.items() if k != "kit_id"})).hexdigest()


def safe_relative(name):
    if not isinstance(name, str) or "\\" in name or "\x00" in name:
        raise KitIntegrityError(f"invalid kit path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(x in {".", ".."} for x in path.parts) or str(path) != name:
        raise KitIntegrityError(f"invalid kit path: {name!r}")
    return path


def contained_file(root, name):
    path = Path(root).joinpath(*safe_relative(name).parts)
    cursor = path
    while cursor != Path(root):
        if cursor.is_symlink():
            raise KitIntegrityError(f"symlink is not a kit source: {name}")
        cursor = cursor.parent
    return path


def _check_entry(entry):
    if not isinstance(entry, dict):
        raise KitIntegrityError("file entry must be an object")
    safe_relative(entry["path"])
    if type(entry["bytes"]) is not int or entry["bytes"] < 0 or not SHA256.fullmatch(entry["sha256"]):
        raise KitIntegrityError("invalid file size/checksum")


def load_manifest(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise KitIntegrityError(f"duplicate manifest key: {key}")
            out[key] = value
        return out

    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)
        if manifest["kit_contract_version"] != KIT_CONTRACT_VERSION or manifest["kit_id"] != manifest_id(manifest):
            raise KitIntegrityError("kit manifest identity/contract mismatch")
        if not re.fullmatch(r"[a-f0-9]{40}", manifest["source_revision"]):
            raise KitIntegrityError("source revision must be a pinned Git commit")
        if not manifest["files"] or not manifest["archives"]:
            raise KitIntegrityError("empty kit inventory or archives")
        names = set()
        kinds = {}
        for entry in manifest["files"]:
            _check_entry(entry)
            if entry["path"] in names or entry["kind"] not in {"code", "data", "wheel"}:
                raise KitIntegrityError("duplicate path or unknown inventory kind")
            kinds[entry["path"]] = entry["kind"]
            prefix = {"data": ("data/",), "wheel": ("wheels/",), "code": ("scripts/", "config/", "docs/", "SANDBOX_START_HERE.md")}[entry["kind"]]
            if not entry["path"].startswith(prefix):
                raise KitIntegrityError("inventory kind/path mismatch")
            names.add(entry["path"])
        _check_entry(manifest["bootstrap"])
        parts = {manifest["bootstrap"]["path"], "kit_manifest.json", "SANDBOX_START_HERE.md"}
        archive_names = set()
        for archive in manifest["archives"]:
            _check_entry(archive)
            if archive["path"] in archive_names:
                raise KitIntegrityError("duplicate archive path")
            archive_names.add(archive["path"])
            if not archive["parts"]:
                raise KitIntegrityError("empty archive parts")
            if sum(part["bytes"] for part in archive["parts"]) != archive["bytes"]:
                raise KitIntegrityError("archive part sizes do not match")
            for part in archive["parts"]:
                _check_entry(part)
                if part["path"] in parts:
                    raise KitIntegrityError("duplicate archive part")
                parts.add(part["path"])
        if not manifest["runtime_targets"]:
            raise KitIntegrityError("no runtime target")
        for key, target in manifest["runtime_targets"].items():
            if key != f"cp{target['python_minor'].replace('.', '')}-linux-x86_64" or target["python_minor"] not in SUPPORTED_PYTHON:
                raise KitIntegrityError("unknown runtime target")
            if not target["wheel_paths"] or not target["packages"] or "pip" not in target["packages"]:
                raise KitIntegrityError("incomplete offline runtime")
            if (kinds.get(target["requirements_path"]) != "code"
                    or any(kinds.get(p) != "wheel" for p in target["wheel_paths"])
                    or len(set(target["wheel_paths"])) != len(target["wheel_paths"])):
                raise KitIntegrityError("runtime inputs absent from inventory")
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError, OverflowError) as exc:
        raise KitIntegrityError(f"malformed kit manifest: {exc}") from exc
    return manifest


def verify_file(root, entry):
    path = contained_file(root, entry["path"])
    if not path.is_file() or path.stat().st_size != entry["bytes"] or hash_file(path) != entry["sha256"]:
        raise KitIntegrityError(f"missing or changed kit file: {entry['path']}")


def verify_inventory(root, manifest, kinds=("code", "data")):
    root = Path(root).resolve()
    selected = [entry for entry in manifest["files"] if entry["kind"] in kinds]
    expected = {entry["path"] for entry in manifest["files"]}
    for entry in selected:
        verify_file(root, entry)
    # Unexpected data shards or Python modules can change provider/execution
    # behavior even while every original file still has its correct checksum.
    for directory in ("scripts", "data", "config"):
        for path in (root / directory).rglob("*"):
            if path.is_symlink():
                raise KitIntegrityError(f"unexpected symlink: {path.relative_to(root)}")
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            name = path.relative_to(root).as_posix()
            if name.startswith("config/strategies/") and path.suffix == ".json":
                continue  # New DSL input is validated, never executable code.
            if name not in expected:
                raise KitIntegrityError(f"unexpected kit source: {name}")


def runtime_key():
    minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    libc, version = platform.libc_ver()
    if (platform.python_implementation() != "CPython" or minor not in SUPPORTED_PYTHON
            or sys.platform != "linux" or platform.machine() != "x86_64"
            or sys.maxsize < 2 ** 32 or libc != "glibc"):
        raise KitEnvironmentError("kit v1 requires CPython 3.11/3.12, Linux x86_64, glibc >= 2.28")
    if tuple(int(x) for x in version.split(".")[:2]) < (2, 28):
        raise KitEnvironmentError("kit wheels require glibc >= 2.28")
    return f"cp{minor.replace('.', '')}-linux-x86_64"


def check_environment(target):
    installed = {}
    for name, expected in target["packages"].items():
        try:
            actual = metadata.version(name)
        except metadata.PackageNotFoundError as exc:
            raise KitEnvironmentError(f"missing pinned package: {name}=={expected}") from exc
        if actual != expected:
            raise KitEnvironmentError(f"package mismatch: {name} requires {expected}, found {actual}")
        installed[name] = actual
    return installed


def assemble_bundle(parts_dir, destination):
    """Verify all transport parts before creating a new destination."""
    parts_dir, destination = Path(parts_dir).resolve(), Path(destination).resolve()
    manifest = load_manifest(parts_dir / "kit_manifest.json")
    key = runtime_key()
    if key not in manifest["runtime_targets"]:
        raise KitEnvironmentError(f"this kit has no offline wheels for {key}")
    if destination.exists():
        raise FileExistsError(f"destination must be new: {destination}")
    verify_file(parts_dir, manifest["bootstrap"])
    for archive in manifest["archives"]:
        for part in archive["parts"]:
            verify_file(parts_dir, part)
    inventory = {entry["path"]: entry for entry in manifest["files"]}
    destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    with tempfile.TemporaryDirectory(prefix="quant-kit-archives-") as temporary:
        for archive in manifest["archives"]:
            combined = Path(temporary) / "combined.zip"
            with combined.open("wb") as stream:
                for part in archive["parts"]:
                    with contained_file(parts_dir, part["path"]).open("rb") as source:
                        shutil.copyfileobj(source, stream)
            if hash_file(combined) != archive["sha256"]:
                raise KitIntegrityError("assembled archive checksum mismatch")
            with zipfile.ZipFile(combined) as packed:
                for info in packed.infolist():
                    name = str(safe_relative(info.filename))
                    if name in seen or name not in inventory or info.file_size != inventory[name]["bytes"]:
                        raise KitIntegrityError(f"unlisted/duplicate/wrong-size archive member: {name}")
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        raise KitIntegrityError("archive symlinks are not supported")
                    seen.add(name)
                    path = contained_file(destination, name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with packed.open(info) as source, path.open("xb") as output:
                        shutil.copyfileobj(source, output)
    if seen != set(inventory):
        raise KitIntegrityError("archive inventory is incomplete")
    shutil.copyfile(parts_dir / "kit_manifest.json", destination / "kit_manifest.json")
    verify_inventory(destination, manifest, ("code", "data", "wheel"))
    return manifest, key


def bootstrap(parts_dir, destination):
    manifest, key = assemble_bundle(parts_dir, destination)
    root = Path(destination).resolve()
    target = manifest["runtime_targets"][key]
    # No system packages, network indexes, implicit dependencies or upgrades.
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(root / ".venv")
    python = root / ".venv/bin/python"
    pip_wheel = next(root / p for p in target["wheel_paths"] if Path(p).name.startswith("pip-"))
    launcher = "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('pip',run_name='__main__')"
    command = [str(python), "-I", "-c", launcher, str(pip_wheel), "--isolated", "install",
               "--no-index", "--no-deps", "--require-hashes", "--find-links", str(root / "wheels"),
               "-r", str(root / target["requirements_path"])]
    process = subprocess.run(command, capture_output=True, text=True)
    (root / "bootstrap_install.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"offline package install failed; inspect {root / 'bootstrap_install.log'}")
    subprocess.run([str(python), "-I", "-m", "pip", "--isolated", "check"], check=True, capture_output=True, text=True)
    process = subprocess.run([str(python), "-I", str(root / "scripts/sandbox_runtime.py"), "verify"],
                             capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError(f"installed kit verification failed: {process.stdout} {process.stderr}")
    result = {"status": "ok", "kit_id": manifest["kit_id"], "runtime": key,
              "root": str(root), "python": str(python), "source_revision": manifest["source_revision"]}
    (root / "bootstrap_ready.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = bootstrap(args.parts_dir, args.destination)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "failed", "phase": "bootstrap", "error": {"type": type(exc).__name__, "message": str(exc)}}))
        raise SystemExit(4)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
