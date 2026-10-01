"""Durable DART source storage; no factor interpretation or PIT certification."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import time
import zipfile


RAW_ROOT = Path(os.environ.get("DART_RAW_ARCHIVE_DIR", "data/financials/dart_raw"))
_budget = float(os.environ.get("DART_COLLECTION_MAX_SECONDS", "0"))
PROCESS_DEADLINE = time.monotonic() + _budget if _budget > 0 else None


class TimeBudgetExceeded(RuntimeError):
    pass


def ensure_time_budget():
    if PROCESS_DEADLINE is not None and time.monotonic() >= PROCESS_DEADLINE:
        raise TimeBudgetExceeded("collection time budget exhausted; no new request dispatched")


@contextmanager
def collector_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("another collector/refresh owns this state; retry after it finishes") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def redacted_error(error):
    text = repr(error)
    secret = os.environ.get("DART_API_KEY", "").strip()
    if secret:
        text = text.replace(secret, "[REDACTED]")
    return re.sub(r"(crtfc_key=)[^&\s'\"<>]+", r"\1[REDACTED]", text)


def atomic_bytes(path, payload, *, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise ValueError(f"immutable source conflict: {path}")
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


def atomic_csv(frame, path):
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    if str(path).endswith(".gz"):
        payload = gzip.compress(payload, mtime=0)
    atomic_bytes(path, payload)


def archive_api_response(task, response):
    # Explicit whitelist: never persist request URLs or crtfc_key.
    request = {key: str(task[key]) for key in ("corp_code", "bsns_year", "reprt_code", "fs_div")}
    value = {"endpoint": "fnlttSinglAcntAll.json", "request": request, "response": response}
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    digest = hashlib.sha256(payload).hexdigest()
    path = RAW_ROOT / "api" / request["bsns_year"] / f"{digest}.json.gz"
    if path.exists():
        if gzip.decompress(path.read_bytes()) != payload:
            raise ValueError("DART API source archive checksum conflict")
        return path, digest
    atomic_bytes(path, gzip.compress(payload, mtime=0), immutable=True)
    return path, digest


def _receipt_dir(receipt):
    if not re.fullmatch(r"\d{14}", str(receipt)):
        raise ValueError("DART document receipt must be 14 decimal digits")
    return RAW_ROOT / "documents" / str(receipt)[:4] / str(receipt)


def archive_document(receipt, payload):
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError("DART original document is not a valid ZIP")
    digest = hashlib.sha256(payload).hexdigest()
    directory = _receipt_dir(receipt)
    path = directory / f"{digest}.zip"
    atomic_bytes(path, payload, immutable=True)
    atomic_json(directory / "latest.json", {"rcept_no": str(receipt), "sha256": digest,
                                             "bytes": len(payload), "file": path.name})
    return path, digest


def cached_document(receipt):
    directory = _receipt_dir(receipt)
    pointer = directory / "latest.json"
    if not pointer.exists():
        return None
    record = json.loads(pointer.read_text())
    digest = record["sha256"]
    if record["rcept_no"] != str(receipt) or not re.fullmatch(r"[a-f0-9]{64}", digest) or record["file"] != digest + ".zip":
        raise ValueError("invalid DART document cache identity")
    payload = (directory / record["file"]).read_bytes()
    if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("DART document cache checksum mismatch")
    return payload, digest


def bounded_results(function, tasks, workers, should_stop):
    """Submit at most workers tasks; stop dispatching after limit/fatal errors.

    Drain already running requests, preserving their results. Never enqueue an
    entire multi-hour batch that continues consuming quota after a stop signal.
    """
    pending = {}
    iterator = iter(tasks)
    def expired():
        return PROCESS_DEADLINE is not None and time.monotonic() >= PROCESS_DEADLINE
    with ThreadPoolExecutor(max_workers=workers) as executor:
        def submit():
            try:
                task = next(iterator)
            except StopIteration:
                return False
            pending[executor.submit(function, task)] = task
            return True
        for _ in range(workers):
            if expired():
                break
            if not submit():
                break
        stopped = False
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                task = pending.pop(future)
                try:
                    result, error = future.result(), None
                except Exception as exc:
                    result, error = None, exc
                stopped = stopped or should_stop(result, error)
                yield task, result, error
            if not stopped:
                if expired():
                    stopped = True
                else:
                    while len(pending) < workers and submit():
                        pass
        if expired():
            raise TimeBudgetExceeded("collection time budget exhausted; checkpoints saved before publication")


class CollectionRun:
    """Atomic heartbeat per collector, distinct from historical task coverage."""
    def __init__(self, path, collector):
        self.path = Path(path)
        self.record = {"contract_version": "1", "collector": collector, "status": "running",
                       "phase": "setup", "started_at_utc": now_utc(), "heartbeat_at_utc": now_utc(),
                       "finished_at_utc": None, "processed_this_run": 0, "checkpoint_count": 0,
                       "error": None}
        self.update()

    def update(self, **values):
        self.record.update(values)
        self.record["heartbeat_at_utc"] = now_utc()
        atomic_json(self.path, self.record)

    def finish(self, status, error=None):
        self.update(status=status, error=error, finished_at_utc=now_utc())
